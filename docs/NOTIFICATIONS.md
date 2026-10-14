# In-app notifications (US-26-T01)

This module lets any authenticated user read the notifications addressed to
them and mark them as read, and gives event producers one entry point to
create notifications. It reuses the existing `notification` table from the
initial schema; migration `5d2f7a9c1e34` only adds the listing index.

US-26 is marked as provisional in the backlog because of its e-mail half
(US-26-T02). This task covers only in-app notifications, which do not depend
on e-mail.

## Endpoints

All routes require `get_current_user`: every account type (candidate,
company in any approval status, administrator) receives notifications, and
every query is scoped to the caller. All responses send
`Cache-Control: no-store`.

1. `GET /api/v1/notifications/me` returns the caller's notifications, newest
   first, plus `unread_count` and `next_cursor`. Query parameters:
   `unread_only` (default `false`), `limit` (1–100, default 20, bounds shared
   with `GET /api/v1/jobs` in `app/core/pagination.py`) and `cursor`.
   Omit `cursor` for the first page and send back the previous `next_cursor`
   for the next one; `next_cursor` is `null` on the last page. The token is
   opaque: clients must not build or parse it. A cursor this API did not
   produce answers `422 invalid_cursor`.
   `unread_count` always counts every unread notification of the caller,
   ignoring the page and the filter, so the client can render a badge from
   the same response.
2. `POST /api/v1/notifications/{notification_id}/read` marks one
   notification as read and returns it. It is idempotent. Another user's
   notification answers `404 notification_not_found`, exactly like a
   nonexistent one, and is left unchanged.
3. `POST /api/v1/notifications/me/read-all` marks every unread notification of
   the caller as read and answers `204`.

## Producing a notification

Producers call
`app.notifications.services.notify_user.notify_user(session, user_id=..., type=..., message=..., details=...)`
inside their own transaction. It only adds the row to the session and never
commits, so the notification exists only if the business change that caused
it is committed.

| Type | Recipient | Producer |
| --- | --- | --- |
| `application_received` | Company that owns the job | `app/applications/services/submit_application.py` |
| `application_status_changed` | Candidate | `app/applications/services/update_application_status.py` |
| `company_registration_rejected` | Company | `app/companies/services/review_company.py` |

`details` carries `application_id` and `job_id` for both application events,
plus the new `status` for `application_status_changed`. The rejection reason
is not copied into the notification: the candidate reads it from their
application list. `company_registration_rejected` carries only `company_id`:
the administrator's free-text reason is the message itself and is not
duplicated in `details`. Rows created before this change may still hold a
`reason` key, which only repeats their own message.

Messages are written in Brazilian Portuguese because they are shown verbatim
in the notification center. Clients that need their own wording can switch
on `type` and `details` instead.

To add an event (US-29 contact, matches for companies, ...):

1. Add a member to
   `app/notifications/domain/notification_type.py::NotificationType`. Its
   value is a stable lowercase `snake_case` code persisted in
   `notification.type` and returned to clients; never rename one.
2. Call `notify_user` from the operation that produces the event, before its
   `commit`.
3. Keep `details` to identifiers the client needs to build a link (for
   example `application_id` or `job_id`). It is returned as-is to the
   notified user: never put personal data, documents or credentials in it.

## Decisions

- **`type` is returned as a string**, not as an enum in the OpenAPI schema.
  The producer signature requires `NotificationType`, but reading stays
  tolerant of a value added by a branch that has not yet registered its
  member, instead of failing the whole list with a `500`.
- **No `read_at` column.** The existing `read` flag is enough for the
  confirmed scope; adding a timestamp would need a migration without a
  consumer.
- **Mark as read uses a single `UPDATE ... RETURNING`** filtered by id and
  owner, so there is no read-check-write race and no row lock is needed.
- **Cursor (keyset) pagination instead of `offset`.** A page holds the
  notifications strictly before the `(created_at, id)` pair of the previous
  page's last item. With an offset, marking items as read under
  `unread_only=true` shifted the remaining ones and skipped unread
  notifications, and a notification arriving between requests repeated an item
  on the next page. `id` breaks ties between equal timestamps, which is common:
  every row created in one transaction shares its `now()`.
- **A late commit can land behind the cursor.** `created_at` is the start time
  of the producing transaction, not its commit time. A transaction that commits
  after a client already paged past that timestamp adds a notification the
  client will not reach by paging forward; it appears the next time the client
  lists from the first page, and `unread_count` includes it immediately.
- **`ix_notification_user_id_created_at_id`** `(user_id, created_at DESC,
  id DESC)` matches the listing order, so a page reads only its rows instead of
  sorting every notification of the user. `ix_notification_user_id_read` stays
  for the unread count.

## Known gaps (out of scope for this task)

- E-mail delivery with `pending`/`sent`/`failed` status (US-26-T02). It will
  hook into `notify_user`; an e-mail failure must not prevent the in-app
  notification.
- Producers for US-29 (contact) and company matches land with those stories.
- A candidate's own withdrawal does not notify the company yet; it was not
  listed among the confirmed events.

## Local verification

```bash
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --no-access-log
```

For automated checks, set `RUN_DATABASE_INTEGRATION_TESTS=1` against an
isolated PostgreSQL 18.4 database and run `uv run python scripts/validate.py`.
