# Job publishing and management (US-17, US-18)

An approved company publishes jobs, lists them in "Minhas vagas", edits them and
closes or reopens them. Every endpoint requires `require_approved_company`: an
anonymous request gets `401`, and a candidate, an administrator or a company
that is not approved gets `403 approved_company_required`. A company reaches
only its own jobs: another company's job answers `404 job_not_found`, the same
as a job that does not exist.

Candidates find published jobs through `GET /jobs`, described in
[JOB_SEARCH.md](JOB_SEARCH.md).

## Endpoints

All paths start with `/api/v1`.

| Endpoint | Success |
| --- | --- |
| `POST /jobs` | `201`: the created job, already `published` |
| `GET /jobs/me` | `200`: every job of the calling company, newest first, with `application_count` |
| `PATCH /jobs/{job_id}` | `200`: the job with its new title, description and skills |
| `PATCH /jobs/{job_id}/status` | `200`: the job closed or reopened |

`POST /jobs` receives:

```json
{
  "title": "Analista de operações",
  "description": "Texto livre, opcional.",
  "skills": [{ "name": "Gestão de equipes", "type": "soft" }],
  "work_mode": "hybrid",
  "closing_date": "2026-12-31"
}
```

- `title`: 1–150 characters after trimming.
- `description`: optional, up to 10,000 characters.
- `skills`: 1–100 items. A name the catalog already knows reuses that entry and
  its stored type; an unknown name creates a catalog skill with the given type.
  See [SKILL_CATALOG.md](SKILL_CATALOG.md).
- `work_mode`: `onsite`, `hybrid` or `remote`.
- `closing_date`: today or later.

Every endpoint returns the same job shape: `id`, `company_id`, `title`,
`description`, `skills` (`id`, `name`, `type`), `work_mode`, `closing_date`,
`status`, `published_at` (null for a job that was never published) and
`created_at`. `GET /jobs/me` adds `application_count`, the number of
applications the job received whatever their status. `POST` and the edit return
the skills in the order they were sent, without repeated names; `GET /jobs/me`
and the status change sort them by name, because the typed order is not stored.

## Editing

`PATCH /jobs/{job_id}` replaces the editable fields, so all three are required:

```json
{
  "title": "Analista de operações sênior",
  "description": "Texto livre; envie \"\" para deixar sem descrição.",
  "skills": [{ "name": "Gestão de equipes", "type": "soft" }]
}
```

The rules are the ones of `POST /jobs`. An omitted `description` is a
`422 validation_error` rather than an erased description. The work mode and the
closing date are not edited here.

## Closing and reopening

`PATCH /jobs/{job_id}/status` receives `{"status": "closed"}` or
`{"status": "open"}`. A reopened job may also receive a new `closing_date`; the
current one is kept when it is omitted, and it is ignored when closing.

"Open" means what the candidate search shows: `published` and not past its
closing date in `America/Sao_Paulo` (`is_open_at`). A closed job leaves the
search, and a reopened one comes back.

| From | `closed` | `open` |
| --- | --- | --- |
| `published`, still open | becomes `closed` | `409 job_already_open` |
| `published`, past its closing date | becomes `closed` | becomes open with a new `closing_date` |
| `paused`, `expired` | becomes `closed` | becomes `published` |
| `closed` | `409 job_already_closed` | becomes `published` |
| `draft`, `under_review` | `409 job_status_change_not_allowed` | `409 job_status_change_not_allowed` |

Reopening with a closing date before today is `422 closing_date_in_the_past`. A
job reopened without a `published_at` gets one.

Closing a job does not change its applications; they keep their status.

## Failures

| Status | `code` | When |
| --- | --- | --- |
| `404` | `job_not_found` | The job does not exist or belongs to another company |
| `409` | `job_already_open`, `job_already_closed` | The job already has the requested status |
| `409` | `job_status_change_not_allowed` | A draft or a job under review |
| `422` | `validation_error` | A field is missing or invalid; `errors` is keyed by location, such as `body.title` or `body.skills.0.name` |
| `422` | `closing_date_in_the_past` | `closing_date` is before today; `errors` is keyed by `closing_date` |
| `500` | `internal_error` | Any unexpected failure, including a lost database connection |

## Transactions

Each write runs in one transaction and locks the job row while it changes it.
Any failure rolls all of it back: a failed publication leaves no job, no job
skill link and no skill created only for that job, and a failed edit keeps the
previous title, description and skills. The interface treats a change as done
only after a success status.

A client that loses the response to a request the server did commit cannot
tell that it succeeded; retrying a publication creates a second job. There is no
idempotency key yet.

## Known limits

- `GET /jobs/me` has no pagination or filters.
- `application_count` counts withdrawn and closed applications too.
- `POST /jobs` compares `closing_date` with the server's calendar date, not the
  `America/Sao_Paulo` date (`app.core.local_date`) that decides whether a job
  is open, so late in the evening in Brazil a closing date of "today" can be
  rejected as past. The status change already uses the local date.
