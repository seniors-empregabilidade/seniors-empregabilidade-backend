# Contact with professionals (US-29-T01)

An approved company sends a message to a professional listed for one of its
jobs. The professional receives it as an in-app notification and by e-mail at
the address on their account; the company never receives that address. Every
contact is recorded in `contact_request`.

The notification and its e-mail reuse US-26 (`notify_user` and the e-mail
dispatcher, see [NOTIFICATIONS.md](NOTIFICATIONS.md)).

## Endpoint

`POST /api/v1/contacts` requires `require_approved_company` and answers `201`
with `Cache-Control: no-store`.

Request:

```json
{
  "job_id": "00000000-0000-4000-8000-000000000001",
  "candidate_id": "00000000-0000-4000-8000-000000000002",
  "message": "Gostaríamos de conversar sobre a vaga."
}
```

`message` has its surrounding spaces removed and must keep 1–2000 characters.
Extra fields are rejected.

Response:

| Field | Meaning |
| --- | --- |
| `id` | The contact record. |
| `job_id`, `candidate_id` | As sent. |
| `created_at` | When the contact was recorded. |
| `email_status` | Always `pending` here: the e-mail is sent after the request by the dispatcher. |

The response carries no data of the professional beyond the id the company
already had.

## Who can be contacted

- The job must belong to the calling company. Another company's job or an
  unknown id answers `404 job_not_found`, the same way as
  `GET /api/v1/jobs/{job_id}/applications`.
- The professional must be in that job's list: an applicant or an automatic
  match (US-19/US-20). Anyone else answers `404 professional_not_found`, so a
  company only reaches people the platform showed it.
- The professional's account must be `active`. A blocked or suspended applicant
  answers `409 professional_unavailable` (US-12). Blocked automatic matches are
  never listed, so they answer `404`.
- The company must be active and approved. A blocked account answers
  `403 account_unavailable` and a company whose registration is not approved
  answers `403 approved_company_required`, both from the auth dependencies.
- The same professional can be contacted again about the same job; each contact
  is a new record and a new notification.

Both accounts are locked with `FOR SHARE` before their status is read inside
the transaction. An administrator's block that commits first is honoured, and a
block issued meanwhile waits until the contact commits. A company blocked
between the auth check and that lock answers `403 account_unavailable`.

Any refusal writes nothing.

## Record

`contact_request`, created in the same transaction as the notification:

| Column | Meaning |
| --- | --- |
| `company_id` | The company that sent the contact. |
| `sent_by_user_id` | The account that sent it. A company has one account today, so it equals `company_id`; set to `null` if that account is deleted. |
| `candidate_id` | The professional contacted. |
| `job_id` | The job the contact is about. |
| `message` | The company's message, stripped. |
| `notification_id` | The notification sent to the professional. Its `email_delivery` row holds the e-mail result (`pending`, `sent` or `failed`, with `attempts` and `last_error`). |
| `created_at` | When the contact was recorded. |

No address, phone or document of the professional is stored. Deleting the
company, the professional or the job removes their contacts with them.

## Notification and e-mail

The notification type is `contact_received`. Its message reads:

```text
<company trade name, or legal name> entrou em contato sobre a vaga "<job title>":

<message>
```

`details` holds only `contact_id` and `job_id`.

Unlike the other US-26 e-mails, this one repeats the notification message,
because delivering the message is the point of the contact. Subject:
"Uma empresa entrou em contato com você". The body contains the text above and
the link to `APP_PUBLIC_URL`.

### Privacy

- The e-mail is built only from the company's public name, the job title and
  the company's own message. Nothing of the professional (name, CPF, phone,
  birth date, address) is read into it.
- The recipient is the professional's account e-mail, read by the dispatcher at
  send time. It never appears in the response, the record or the logs.
- The company's free text is not filtered. It reaches only the professional,
  who is its intended reader.

### E-mail failure

The e-mail goes through the US-26 dispatcher after the commit. A failure keeps
the delivery `pending` and retries it, then marks it `failed`; the
notification and the contact record are never changed. Real sending follows the
US-26 configuration: while production keeps `EMAIL_BACKEND=log` and the
dispatcher off, deliveries stay `pending`.

## Error codes

| Status | Code | When |
| --- | --- | --- |
| 401 | `invalid_access_token` | Missing or invalid access token. |
| 403 | `account_unavailable` | The company account is blocked or suspended. |
| 403 | `approved_company_required` | The caller is not an approved company. |
| 404 | `job_not_found` | The job does not exist or belongs to another company. |
| 404 | `professional_not_found` | The professional is not in the job's list. |
| 409 | `professional_unavailable` | The professional's account is blocked or suspended. |
| 422 | `validation_error` | Invalid ids, blank or too long message, or an extra field. |

## Known gaps (out of scope for this task)

- There is no endpoint listing a company's contacts or exposing the e-mail
  result; both are only in the database.
- The professional cannot reply through the platform or the e-mail. The e-mail
  has no `Reply-To` and its footer says that replies do not reach the company
  and that the professional should answer through the channel the company
  gives in its message. The company includes that channel if it wants an
  answer.

## Local verification

```bash
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --no-access-log
```

For automated checks, set `RUN_DATABASE_INTEGRATION_TESTS=1` against an
isolated PostgreSQL 18.4 database and run `uv run python scripts/validate.py`.
