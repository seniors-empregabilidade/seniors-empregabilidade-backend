# Candidate applications: submit, list, and withdraw (US-12-T01, US-13-T01)

This module lets an authenticated candidate apply to an open job, read their
own applications, and leave an active selection process. It reuses the
existing `application`, `job`, `company`, `job_skill`, `resume`, `resume_skill`
and `skill` persistence models, and the `app/jobs` (job publishing, #23) and
`app/skills` (catalog, #25) product modules; it does not introduce a new
domain.

## Endpoints

1. `POST /api/v1/applications` requires `require_candidate`. It registers the
   caller's application to `job_id` (never a candidate ID from the request
   body — that is always the authenticated caller). The job must be open
   (published, within `closing_date`, and owned by a company whose account is
   not `blocked`); a duplicate application to the same job, by the same
   candidate, is rejected. See "Decisions" below for the
   compatibility calculation and the concurrency guarantee.
2. `GET /api/v1/applications/me` requires `require_candidate`. It returns every
   application owned by the caller — never another candidate's — each with the
   job title, the company display name (trade name, falling back to legal
   name), the submission date, days in process, and status. An optional
   `company_name` query parameter filters by a case-insensitive partial match
   against that same company display name.
3. `POST /api/v1/applications/{application_id}/withdraw` requires
   `require_candidate`. It moves an active application (`applied`,
   `under_review` or `in_selection_process`) to `withdrawn` and stamps
   `closed_at`. It is intentionally irreversible: there is no endpoint to
   undo a withdrawal.

All three endpoints send `Cache-Control: no-store`, matching the rest of the
identity surface.

## Decisions

- **An application's initial status is `under_review`** ("em análise"),
  chosen from the existing `application_status` enum instead of adding a new
  value. It is already one of the statuses `withdraw_application` treats as
  active, so a freshly submitted application can be withdrawn right away.
- **An open job is published, within its closing date, and owned by a company
  whose account is not `blocked`.** The date criterion is the one
  `find_similar_jobs` already used: `Job.status == PUBLISHED` and
  `Job.closing_date >= today` (`today` from `to_local_date`, see below).
  `submit_application` reuses it. A blocked company account answers
  `409 job_not_open` and creates no application; the job itself is left
  `published`. The company `app_user` row is locked before that check, so a
  block that commits first is the status this request observes. Reactivating
  the account makes that job applicable again while it is still within
  `closing_date`. See [ACCOUNT_MANAGEMENT.md](ACCOUNT_MANAGEMENT.md).
- **Compatibility ("matches X of Y requirements") is computed once, at
  submission time, and never recalculated.** `matched_requirements` and
  `total_requirements` (added by migration `b8c94551d715`) are plain
  `SmallInteger` columns, both nullable to accommodate rows written before
  this migration. `X`/`Y` are stored explicitly, rather than only a
  percentage, so a later read of the same application is unaffected by the
  job's required skills or the candidate's resume skills changing afterward.
  `application.match_score` — a pre-existing 0-100 percentage column with no
  producer — is left untouched; see "Known gaps".
- **The matching itself
  (`app/applications/domain/policies/requirement_match.py::match_requirements`)
  is a provisional US-10 stand-in**: a plain set intersection between the
  job's required skill IDs (`job_skill`) and the candidate's resume skill IDs
  (`resume_skill`, through the candidate's `resume`), with every skill
  weighted equally regardless of type (hard/soft) or importance. This mirrors
  the same provisional pattern already used by `find_similar_jobs` for
  US-17-T01/US-10-T01. A candidate with no resume yet is treated as having no
  skills (`matched = 0`), not as an error.
- **Duplicate applications are prevented by the database, not by a
  pre-check.** The `(candidate_id, job_id)` unique constraint
  (`uq_application_candidate_id_job_id`) already existed in the initial
  schema. `submit_application` still validates the job first (existence,
  open state) for a clear `404`/`409`, then relies on this constraint for the
  actual insert: under concurrency, two simultaneous requests both pass the
  earlier checks, but only one `INSERT` can succeed. The other's
  `IntegrityError` is translated into `409 application_already_exists`
  (matching the constraint-name lookup pattern in
  `app/candidates/services/register_professional.py`), instead of allowing a
  second row or crashing with a raw database error.
- **Days in process** counts calendar dates, not hours: from the submission
  date (`application.created_at`) up to today while the application is still
  active, or up to the closing date once it left the pipeline. A candidate who
  withdrew last week does not keep accruing days just because they open the
  list today. See `app/applications/domain/policies/days_in_process.py`.
- **Calendar dates are computed in `America/Sao_Paulo`, not UTC.** Both sides
  of every date comparison in this module (days in process, and "is this job
  still open") go through
  `app/core/local_date.py::to_local_date`, which
  converts an aware `datetime` via `ZoneInfo("America/Sao_Paulo")` before
  calling `.date()`. A timestamp stored at 02:00 UTC is already "yesterday
  evening" in that timezone; comparing raw UTC dates would silently shift
  those boundary cases by a day. `ZoneInfo` works in this environment: on
  Windows, `tzdata` is already present as a transitive dependency of
  `psycopg` (see `uv.lock`); on Linux/macOS the system tz database is used.
  No new dependency was added for this.
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
- **Suggestions are shown only for `not_selected`** applications, per the
  confirmed scope. Active applications and applications the candidate
  withdrew never include any.
- **Services return their own value objects, not HTTP DTOs.**
  `list_my_applications` and `withdraw_application` return
  `app.applications.services.application_summary.ApplicationSummary`
  (a plain, frozen dataclass with no Pydantic/FastAPI dependency);
  `submit_application` returns its own `SubmittedApplication` the same way;
  `find_similar_jobs` returns `list[SimilarJob]` from the same layer. None of
  these services import a Pydantic schema. `app/applications/router.py` maps
  those values to `ApplicationSummaryResponse` / `ApplicationResponse` /
  `SimilarJobResponse` for the public contract, following
  `docs/development/use-cases.md` and mirroring `publish_job.py`'s
  `PublishedJob` value.

## Automatic applications

The platform applies on a professional's behalf when their compatibility with an
open job reaches a threshold. It is one job (`app/applications/services/
generate_automatic_applications.py`) with two triggers:

- **When a job is published.** `POST /api/v1/jobs` schedules the evaluation as a
  background task after the `201`, so it never delays or fails the company's
  request (a failure is logged as `automatic_applications_failed`). Every eligible
  professional already registered is evaluated.
- **Daily.** A loop started with the API (`AutomaticApplicationScheduler`, same
  shape as the e-mail dispatcher) evaluates every open job for professionals whose
  account was created after the job. Earlier accounts were already evaluated when
  the job was published. It runs once at startup and then every
  `AUTOMATIC_APPLICATION_INTERVAL_SECONDS`; running again is harmless.

Rules:

- Compatibility is `JobCompatibilityPolicy` (US-19). The professional qualifies
  when `matched / required >= threshold`, compared on the exact ratio
  (`qualifies_for_automatic_application`). A job without required skills is skipped.
- Only open jobs: published, within the closing date, company not `blocked`.
- Only professionals with an `active` account, `available`, and
  `candidate.accepts_automatic_application` on. The column defaults to `true`;
  the migration also turned it on for existing rows, since nothing could set it
  before. Turning it off (T05) stops new automatic applications and does not
  withdraw existing ones.
- No duplicates: a professional with any application to the job, in any status,
  is skipped, and the insert uses `ON CONFLICT DO NOTHING` on the
  `(candidate_id, job_id)` unique constraint, so overlapping runs cannot create two.
- The application is stored with `type = automatic`, `status = under_review` and
  the requirement counts, exactly like a manual one otherwise. It does not notify
  the company: it appears in the job's applicants list (US-20).

| Variable | Default | Effect |
| --- | --- | --- |
| `AUTOMATIC_APPLICATION_THRESHOLD_PERCENT` | `70` | Minimum compatibility, 1 to 100 |
| `AUTOMATIC_APPLICATION_ENABLED` | `false` | Starts the daily loop with the API |
| `AUTOMATIC_APPLICATION_INTERVAL_SECONDS` | `86400` | Pause between daily rounds |

The loop is off by default, as for e-mail: set `AUTOMATIC_APPLICATION_ENABLED=true`
in the deployed configuration. The job-published trigger does not depend on it.

## Known gaps (out of scope for this task)

- **No closing reason is exposed yet.** `ApplicationSummaryResponse` has no
  `closed_reason` field: nothing in the codebase currently transitions an
  application to `hired`, `not_selected` or `expired`, so there is no producer
  for a rejection reason. The field will come back together with a future
  company-side "reject candidate" action (US-21), which will also need to add
  the column where that reason is stored (this task deliberately does not add
  a speculative column or field for it) and to populate `application.closed_at`
  too.
- **No shared skill-matching/compatibility engine exists yet
  (US-17-T01/US-10-T01).** `app/jobs` (#23) covers publishing a job and
  `app/skills` (#25) covers the skill catalog, but neither compares a job's
  requirements against a candidate's resume with anything beyond a plain
  ID intersection. `find_similar_jobs` (suggestions) and
  `match_requirements` (compatibility, this task) are both provisional
  stand-ins built directly on `job_skill`/`resume_skill`; replace their
  bodies once the real engine exists — callers do not need to change.
- **`application.match_score` still has no producer.** It is a pre-existing
  0-100 percentage column; this task populates the more specific
  `matched_requirements`/`total_requirements` counts instead, since a single
  percentage cannot losslessly represent "X of Y". Whoever defines the
  formula and consumer for `match_score` (e.g., company-side ranking in
  US-21) can derive it from these two counts, or from the real US-10 engine
  once it exists.
- **A candidate can apply without a résumé.** `submit_application` treats a
  missing `resume` row as zero candidate skills (`matched_requirements = 0`),
  not as an error; nothing in the confirmed scope requires a résumé before
  applying.
- **Similar jobs rank by shared skills, not by the candidate's match.**
  `app/applications/services/find_similar_jobs.py` ranks other open jobs by
  how many skills they share with the source job, excluding that job itself
  and every job the candidate already applied to, capped at 5 suggestions.
  "Open" comes from `app.jobs.services.is_open_at`, the same rule the job
  search uses (see `docs/JOB_SEARCH.md`), and it also omits a job whose
  company account is `blocked`. It does not use the candidate
  compatibility policy of the search: it compares two jobs, and its ranking
  and limit run in SQL.

## Local verification

```bash
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --no-access-log
```

Open `/docs`, authorize with a candidate access token, then call
`POST /api/v1/applications` (body: `{"job_id": "<uuid of an open job>"}`),
`GET /api/v1/applications/me` (optionally with `?company_name=...`), and
`POST /api/v1/applications/{application_id}/withdraw`.

For automated checks, set `RUN_DATABASE_INTEGRATION_TESTS=1` against an
isolated PostgreSQL 18.4 database and run `uv run python scripts/validate.py`.
