# Account management

This module lets an administrator list candidate and company accounts and
block or reactivate them. It reuses the existing `app_user`, `candidate`,
`company`, `resume` and `event` tables; it adds no table or column.

Administrators are never listed and cannot be targeted. Blocking takes effect
on the next authenticated request: `get_current_user` answers
`403 account_unavailable` until the account is active again.

## Endpoints

Both routes require `require_administrator`. A missing or invalid token answers
`401 invalid_access_token`. A candidate or a company answers
`403 administrator_required`. A suspended or blocked caller answers
`403 account_unavailable`. Every response sends `Cache-Control: no-store`.

1. `GET /api/v1/admin/accounts` returns one page of accounts and the total
   number of accounts matching the filters, newest first. `total` counts every
   match, not the page, so the client can tell when it has reached the end.
2. `GET /api/v1/admin/accounts/{account_id}` returns the registration shown in
   the management modal. An unknown id and an administrator id both answer
   `404 account_not_found`.
3. `PATCH /api/v1/admin/accounts/{account_id}/status` sets that account to
   `active` or `blocked` and returns `{id, account_status}`. The modal uses
   `blocked` to block and `active` to reactivate; both require `reason`.

## Filters

All filters are optional and combine with `AND`. Invalid values answer
`422 validation_error` with the field under `errors` (for example
`query.account_status`) before any listing runs.

| Query parameter | Type | Default | Rule |
| --- | --- | --- | --- |
| `user_type` | `candidate` or `company` | none | Omit it to list both. `administrator` is rejected. |
| `account_status` | `active`, `suspended` or `blocked` | none | Matches `app_user.account_status`. This module only writes `active` and `blocked`; `suspended` remains filterable because the column allows it. |
| `company_status` | `pending`, `approved`, `rejected` or `blocked` | none | Matches `company.status`. Candidates have no company row, so they never match. This is the company's approval situation, not `app_user.account_status`. |
| `min_completion` | integer | none | 0–100. With `max_completion`, keeps candidates whose résumé completion is inside the range. A candidate with no résumé counts as `0`. |
| `max_completion` | integer | none | 0–100. See `min_completion`. When only one bound is sent, the other is `0` or `100`. |
| `limit` | integer | 20 | From 1 to 100. |
| `offset` | integer | 0 | From 0 to 2^63 - 1 (PostgreSQL `bigint`). |

`min_completion` greater than `max_completion` answers `422
invalid_completion_range`, with the message under `errors.query.min_completion`.
A completion bound also forces `user_type = candidate`, so combining one with
`user_type=company` returns an empty page.

Results are ordered by `created_at` descending, then `id`.

Each item:

| Field | Meaning |
| --- | --- |
| `id` | `app_user.id`. For a company this is also `company.id`. |
| `user_type` | `candidate` or `company`. |
| `email` | The account email. |
| `display_name` | The candidate's full name, or the company's trade name, or its legal name. `null` when none of those exist. |
| `account_status` | `active`, `suspended` or `blocked`. |
| `company_status` | The company's approval situation; `null` for a candidate. |
| `completion_percentage` | The candidate's résumé completion, `0` when they have no résumé; `null` for a company. |
| `created_at` | When the account was created. |

## Registration detail

`GET /api/v1/admin/accounts/{account_id}` fills the management modal. It does
not return the CPF, phone, birth date, salary, street address, CNAE, LinkedIn,
terms acceptance, or any stored justification. A company has no résumé, so
`summary` is `null`, `completion_percentage` and `application_count` are
`null`, and the three lists are empty. A candidate has no company profile, so
the company fields below are `null`.

| Field | Meaning |
| --- | --- |
| `id`, `user_type`, `email`, `display_name`, `account_status`, `company_status`, `completion_percentage`, `created_at` | Same meaning as a list item. |
| `application_count` | Applications the candidate has submitted. `null` for a company. |
| `summary` | The résumé summary. `null` when there is no résumé, or the account is a company. |
| `experiences` | `{id, role, company_name, start_date, end_date}`, newest start date first. `end_date` is `null` when the role is current. |
| `education` | `{id, institution, degree, field, start_date, end_date}`, newest start date first. |
| `skills` | `{id, name}`, ordered by name. |
| `legal_name` | Company legal name. `null` for a candidate. |
| `trade_name` | Company trade name. `null` when unset or the account is a candidate. `display_name` prefers this over `legal_name`. |
| `cnpj` | Company CNPJ. `null` for a candidate. |
| `corporate_email` | Company corporate email. `null` for a candidate. |
| `city`, `state` | City and state code from the company address. `null` when there is no address, or the account is a candidate. |
| `industry`, `company_size` | Company industry and size. `null` when unset or the account is a candidate. |
| `published_job_count` | Jobs whose status is `published`. Draft, paused, expired and closed jobs are left out. `null` for a candidate. |

The modal blocks with `PATCH .../status` and `{"status": "blocked", "reason": "..."}`.
It reactivates with `{"status": "active", "reason": "..."}`. Which action to
offer follows `account_status` from this response.

## Status change

The body is `{status, reason}`. `status` is `active` or `blocked`; `suspended`
is rejected. `reason` is required, surrounding spaces are removed, and the
stored text is 1–500 characters. Extra fields are rejected. A malformed
`account_id` answers `422 validation_error`.

The account row is locked (`SELECT ... FOR UPDATE`) for the change. An unknown
id and an administrator id both answer `404 account_not_found`; nothing is
written. Repeating the current status answers `409 account_already_blocked` or
`409 account_already_active` and writes no `event` row.

Blocking or reactivating a **company** does not close its jobs and does not
change applications already submitted. While `account_status` is `blocked`:

- `search_jobs` (`GET /api/v1/jobs`) omits that company's jobs;
- `find_similar_jobs` omits them from suggestions;
- `submit_application` (`POST /api/v1/applications`) locks that company
  account and then answers `409 job_not_open`, inserting nothing. A block
  that commits first is the status the application observes.

The job stays `published`. Reactivating the account lists and accepts it again
while it is still open (published and within `closing_date`). See
[JOB_SEARCH.md](JOB_SEARCH.md) and [APPLICATIONS.md](APPLICATIONS.md).

## Event record

The change and its `event` row commit in the same transaction. The row is the
administrative log; it is not returned by the API.

| Column | Value |
| --- | --- |
| `id` | Generated UUID. |
| `user_id` | The administrator who made the change, not the target account. Deleting that administrator sets this column to `null`. |
| `event_type` | `account_blocked` when the new status is `blocked`; otherwise `account_reactivated`. |
| `created_at` | The database clock at insert. |
| `details` | The JSON object below. |

```json
{
  "target_user_id": "00000000-0000-4000-8000-00000000a001",
  "previous_status": "active",
  "new_status": "blocked",
  "reason": "Synthetic abuse report."
}
```

`target_user_id`, `previous_status` and `new_status` are strings. `reason` is
the stripped justification from the request. No other key is written. The
reason is not copied onto the account and is not present in the status
response.

## Error codes

| Status | Code | When |
| --- | --- | --- |
| 401 | `invalid_access_token` | Missing or invalid access token. |
| 403 | `account_unavailable` | The caller's own account is suspended or blocked. |
| 403 | `administrator_required` | The caller is a candidate or a company. |
| 404 | `account_not_found` | The target does not exist or is an administrator. |
| 409 | `account_already_blocked` | The account is already `blocked`. |
| 409 | `account_already_active` | The account is already `active`. |
| 422 | `validation_error` | A query parameter, path id or body field is invalid. |
| 422 | `invalid_completion_range` | `min_completion` is greater than `max_completion`. |

Failures use `application/problem+json`. A rejected change leaves the account
and `event` untouched.

## Local verification

```bash
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --no-access-log
```

Open `/docs`, authorize with an administrator access token, then call
`GET /api/v1/admin/accounts`,
`GET /api/v1/admin/accounts/{account_id}`, and
`PATCH /api/v1/admin/accounts/{account_id}/status`.

For automated checks, set `RUN_DATABASE_INTEGRATION_TESTS=1` against an
isolated PostgreSQL 18.4 database and run `uv run python scripts/validate.py`.
