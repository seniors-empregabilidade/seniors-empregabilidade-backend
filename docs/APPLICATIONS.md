# Candidate application list and withdrawal (US-13-T01)

This module lets an authenticated candidate read their own applications and
leave an active selection process. It reuses the existing `application`, `job`,
`company`, `job_skill` and `skill` persistence models; it does not introduce a
new domain.

## Endpoints

1. `GET /api/v1/applications/me` requires `require_candidate`. It returns every
   application owned by the caller — never another candidate's — each with the
   job title, the company display name (trade name, falling back to legal
   name), the submission date, days in process, and status. An optional
   `company_name` query parameter filters by a case-insensitive partial match
   against that same company display name.
2. `POST /api/v1/applications/{application_id}/withdraw` requires
   `require_candidate`. It moves an active application (`applied`,
   `under_review` or `in_selection_process`) to `withdrawn` and stamps
   `closed_at`. It is intentionally irreversible: there is no endpoint to
   undo a withdrawal.

Both endpoints send `Cache-Control: no-store`, matching the rest of the identity
surface.

## Decisions

- **Days in process** counts calendar dates, not hours: from the submission
  date (`application.created_at`) up to today while the application is still
  active, or up to the closing date once it left the pipeline. A candidate who
  withdrew last week does not keep accruing days just because they open the
  list today. See `app/applications/domain/policies/days_in_process.py`.
- **`application.closed_at`** (added by migration `1c381f6d0f82`) records the
  moment an application became terminal. It exists because `updated_at` has no
  `onupdate` trigger in this schema and therefore cannot substitute as a
  closing timestamp. Any future transition into a terminal status (hired,
  not_selected, expired) should set this column too; today only the candidate
  withdrawal endpoint does.
- **Ownership check returns `404`, not `403`.** Looking up the application by
  `id` filtered by the caller's `candidate_id` in the same query means a
  request for someone else's application matches no row: it is
  indistinguishable from a nonexistent application, and nothing is changed.
- **Withdrawal concurrency safety.** The update runs inside one transaction
  that locks the application row (`SELECT ... FOR UPDATE`) before checking its
  status. A second concurrent request blocks until the first commits, then
  observes the already-closed status and receives
  `409 application_already_closed` instead of double-withdrawing.
- **Suggestions and a closing reason are shown only for `not_selected`**
  applications, per the confirmed scope. Active applications and applications
  the candidate withdrew never include either field.

## Known gaps (out of scope for this task)

- **No closing reason is ever persisted yet.** `closed_reason` is always
  `null` today: nothing in the codebase currently transitions an application
  to `hired`, `not_selected` or `expired`, so there is no producer for a
  rejection reason. A future company-side "reject candidate" action must add
  where that reason is stored (this task deliberately does not add a
  speculative column for it) and populate `application.closed_at` too.
- **No shared skill-matching engine exists (US-17-T01/US-10-T01).** There is
  no jobs or skills product module yet, only the `job`, `skill` and
  `job_skill` persistence models. `app/applications/services/find_similar_jobs.py`
  is a provisional, minimal stand-in: it ranks other published jobs by a plain
  skill-id set intersection with the source job, excluding that job itself and
  every job the candidate already applied to, capped at 5 suggestions. Replace
  its body with the shared engine once it exists; callers do not need to
  change.
- **There is no "apply to a job" endpoint yet.** This task only lists and acts
  on applications that already exist; test fixtures insert `application` rows
  directly, mirroring `scripts/seed.py`.

## Local verification

```bash
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --no-access-log
```

Open `/docs`, authorize with a candidate access token, then call
`GET /api/v1/applications/me` (optionally with `?company_name=...`) and
`POST /api/v1/applications/{application_id}/withdraw`.

For automated checks, set `RUN_DATABASE_INTEGRATION_TESTS=1` against an
isolated PostgreSQL 18.4 database and run `uv run python scripts/validate.py`.
