# Job publishing and management (US-17, US-18)

An approved company publishes jobs, lists them in "Minhas vagas", edits them and
closes or reopens them. Every endpoint requires `require_approved_company`: an
anonymous request gets `401`, and a candidate, an administrator or a company
that is not approved gets `403 approved_company_required`. A company reaches
only its own jobs: another company's job answers `404 job_not_found`, the same
as a job that does not exist.

Candidates find published jobs through `GET /jobs`, described in
[JOB_SEARCH.md](JOB_SEARCH.md), and read one job through
`GET /jobs/{job_id}`, described below.

## Job detail (US-11-T01)

`GET /api/v1/jobs/{job_id}` requires `require_candidate` (`401` anonymous,
`403 candidate_required` otherwise) and is sent with `Cache-Control: no-store`.
It returns `id`, `title`, `description`, `company_id`, `company_name` (trade
name, else legal name), `skills` (`id`, `name`, `type`: the job has no separate
requirements field, so `hard` skills are the requirements and `soft` ones the
competencies), `work_mode`, `location`, `closing_date` (the deadline), `status`,
`published_at`, and the candidate's state:

| Field | Meaning |
| --- | --- |
| `already_applied` | The caller has an application to the job, whatever its status (withdrawn included, since `(candidate_id, job_id)` is unique). |
| `is_open` | `published` and not past its closing date in `America/Sao_Paulo`. |
| `is_expired` | Status `expired`, or `published` but past its closing date. |
| `is_applicable` | `is_open` and not `already_applied`. A closed, paused or expired job is never applicable. |

A draft, a job under review, a job of a `blocked` company account and an unknown
id answer `404 job_not_found`. Other statuses are readable, so a candidate can
still see a job that closed after they applied.

## Endpoints

All paths start with `/api/v1`.

| Endpoint | Success |
| --- | --- |
| `POST /jobs` | `201`: the created job, already `published` |
| `GET /jobs/me` | `200`: every job of the calling company, newest first, with `application_count` |
| `PATCH /jobs/{job_id}` | `200`: the job with its new title, description and skills |
| `PATCH /jobs/{job_id}/status` | `200`: the job closed or reopened |
| `GET /jobs/{job_id}/applications` | `200`: the job's applicants and automatic matches ranked by compatibility (US-19, US-20) |

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

## Applicants ranked by compatibility (US-19)

`GET /jobs/{job_id}/applications` lists everyone who applied to the job, whatever
the application status, with a header (`total_applicant_count`,
`full_match_count`) and one row per applicant: `application_id`, `status`,
`match_score`, `compatibility_percentage`, `is_highlighted`,
`matched_skill_count`, `required_skill_count` and a `profile` limited to
`candidate_id`, `full_name`, `city` and `state`.

The ranking comes from `app.jobs.domain.policies.job_compatibility_policy`,
comparing the job's skills (`job_skill`) with the applicant's résumé skills
(`resume_skill`) by catalog id:

- `compatibility_percentage` is matched required skills / required skills * 100,
  rounded half up to two decimal places and serialized as a string (`"66.67"`).
  Skills beyond the job's do not count; an applicant without a résumé scores
  `"0.00"`.
- `is_highlighted` is `true` from 50% up, compared on the exact ratio.
- `matched_skills` and `missing_skills` name the criteria behind the
  percentage: the job's required skills found and not found on the résumé, each
  `{id, name}`, ordered by name. Both are empty when the job has no required
  skills.
- Rows are ordered by `compatibility_percentage` descending; equal percentages
  keep the application order (oldest first). Highlighted applicants come first
  and the ones below 50% follow them in the same list.
- A job without required skills cannot be scored: its applicants keep the
  application order (oldest first) with `compatibility_percentage: null`,
  `is_highlighted: false` and zero counts. Published jobs always have skills.
- `match_score` is the stored `application.match_score` column, which still has
  no producer (see [APPLICATIONS.md](APPLICATIONS.md)); it no longer drives the
  order.

The percentage is computed on every request from the current job and résumé
skills, unlike `matched_requirements`/`total_requirements`, which the application
stores at submission time.

## Origin: applications and automatic matches (US-20)

The same list also shows professionals who did not apply but are compatible
with the job, and every row carries an `origin`:

- `application`: the professional applied, whatever the application status
  (a withdrawn applicant is still an application).
- `automatic_match`: the professional has not applied and the compatibility
  engine highlights them (50% or more, `is_automatic_match` in
  `app.jobs.domain.policies.automatic_match_policy`). Only candidates whose
  account is `active` and whose `availability` is `available` are considered.
  `application_id`, `status` and `match_score` are `null`.

Both origins go through the same `JobCompatibilityPolicy` with the same inputs,
so applying never changes `compatibility_percentage`, `is_highlighted` or the
counts: two professionals with the same résumé skills get the same values
whatever their origin. Rows are ranked together by percentage; on equal
percentages applicants come first (oldest application first), then automatic
matches by `candidate_id`. A job without required skills has no automatic
matches.

An automatic match exposes the same `profile` as an applicant (`candidate_id`,
`full_name`, `city`, `state`); contact and identification data (email, phone,
CPF, birth date) are never returned for either origin. Contacting a
professional is a separate story (US-29).

The header keeps `total_applicant_count` and `full_match_count` for
applications only and adds `automatic_match_count`.

### Automatic application opt-in (US-20-T05)

`GET /api/v1/professionals/me` returns `accepts_automatic_application`, and
`PATCH /api/v1/professionals/me` accepts it as `true` or `false` (`null` is
rejected). It starts with the column default, which US-20-T04 turns on, and the
professional can turn it off at any time. US-20-T04 reads it to decide who is
applied automatically; turning it off stops new applications from the next cycle.

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
