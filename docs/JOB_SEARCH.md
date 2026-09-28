# Job search (US-10-T01)

This endpoint lets an authenticated candidate search open jobs by title and see,
for each one, how many of its required skills the candidate's résumé meets and
which ones are missing. It reuses the `job`, `job_skill`, `skill`, `company`,
`resume` and `resume_skill` persistence models; it adds no table or column.

## Endpoint

`GET /api/v1/jobs` requires `require_candidate`: anonymous callers get
`401 invalid_access_token`, companies and administrators get
`403 candidate_required`.

| Query parameter | Type | Default | Rule |
| --- | --- | --- | --- |
| `search` | string | none | Optional, at most 150 characters. Surrounding spaces are ignored; a blank value lists every open job. Otherwise a job matches when its title contains the text, ignoring letter case. `%` and `_` are literal. |
| `limit` | integer | 20 | From 1 to 100. |
| `offset` | integer | 0 | From 0 to 2^63 - 1 (PostgreSQL `bigint`). |

The response is a JSON array (`200`), possibly empty, sent with
`Cache-Control: no-store` because it is built from the caller's résumé. Results
are ordered by:

1. `matched_skill_count`, highest first;
2. `published_at`, most recent first, jobs without a publication date last;
3. `id`, so pages never overlap or skip a job.

There is no total count: a page shorter than `limit` is the last one.

Each item:

| Field | Meaning |
| --- | --- |
| `id`, `title` | The job. |
| `company_name` | The company's trade name, or its legal name when it has none. No other company field is returned. |
| `location` | Nullable. See known gaps. |
| `work_mode` | `onsite`, `hybrid` or `remote`. |
| `salary_max` | Nullable decimal string with two places. The job stores only a ceiling, not a range. |
| `published_at` | Nullable timestamp. |
| `days_since_published` | Calendar days from `published_at` to today in `America/Sao_Paulo`; `null` when `published_at` is. |
| `matched_skill_count` | How many of the job's skills are on the candidate's résumé (the X in "meets X of Y requirements"). |
| `required_skill_count` | How many skills the job requires (the Y). |
| `missing_skills` | The job's skills the candidate lacks, as `{id, name, type}`, ordered by name. |

Example, `GET /api/v1/jobs?search=analyst&limit=20&offset=0`:

```json
[
  {
    "id": "00000000-0000-4000-8000-00000000f001",
    "title": "Python Data Analyst",
    "company_name": "Example Company",
    "location": "Porto Alegre",
    "work_mode": "hybrid",
    "salary_max": "6500.00",
    "published_at": "2026-09-24T22:06:01.689045Z",
    "days_since_published": 2,
    "matched_skill_count": 1,
    "required_skill_count": 2,
    "missing_skills": [
      {
        "id": "00000000-0000-4000-8000-00000000e001",
        "name": "Excel",
        "type": "hard"
      }
    ]
  }
]
```

Invalid parameters return `422 validation_error` with the field under `errors`
(for example `query.limit`), before any search runs.

## Decisions

- **"Open" has one definition.** A job is open when it is `published` and its
  `closing_date` is today or later, today being the calendar date in
  `America/Sao_Paulo`. `app/jobs/services/open_job.py::is_open_at` holds that
  rule, and both this search and `find_similar_jobs` use it. There is no
  "Aberta" status in `JobStatus`; the card's "Aberta" is this rule.
- **`to_local_date` moved to `app/core/local_date.py`.** It used to live in
  `app/applications/domain/policies`; the jobs module needs it too, and one
  module must not import another's private code.
- **Compatibility is a pure policy.**
  `app/jobs/domain/policies/skill_match.py::match_skills` receives two sets of
  catalog `skill_id`s and returns the matched and required counts and the missing
  ids. Skills are compared by id, never by name: `skill.normalized_name` is
  unique, and `job_skill` and `resume_skill` point to the same catalog. A
  candidate without a résumé or without skills matches zero, which is not an
  error.
- **The ordering count runs in SQL.** Sorting by compatibility before paginating
  needs the count for every open job, so the query counts the job's skills that
  are on the résumé. The policy then computes the returned numbers for the
  page's jobs only. Both use the résumé skills read once per request.
- **Numbers, not the sentence.** The API returns `matched_skill_count` and
  `required_skill_count`; the "atende X dos Y requisitos" wording belongs to the
  frontend.
- **Pagination.** The card does not mention it; an unbounded search could exhaust
  the 0.5 GiB production instance, so `limit` defaults to 20 and caps at 100.
- **No title index.** Measured with `EXPLAIN ANALYZE` on a local PostgreSQL 18.6
  loaded with 10,000 extra jobs (8,000 open) and 30,000 job skills: the title
  filter scanned every job sequentially in 7 ms, and the unfiltered first page,
  which counts matches for every open job, took 37 ms. A trigram
  index would need an extension and a migration for no measurable gain today.
- **A search containing NUL finds nothing** instead of reaching the database,
  which rejects that character; no stored title can contain it.

## Known gaps (out of scope for this task)

- **`location` and `salary_max` are always null for jobs published through the
  API.** `POST /api/v1/jobs` (US-17-T01) does not collect them yet; only the
  seed fills them. US-17 needs to start collecting them. The job stores only a
  salary ceiling, so the card's "salary range" is that ceiling.
- **The search ignores case but not accents.** "gestao" does not find
  "Gestão". Accent-insensitive search would need the `unaccent` extension or a
  normalized title column, both a migration.
- **The company's approval status is not checked.** Like `find_similar_jobs`,
  the search lists open jobs whatever their company's current status is.

## Local verification

```bash
uv sync --frozen
docker compose up -d
uv run alembic upgrade head
uv run python scripts/seed.py
uv run uvicorn app.main:app --no-access-log
```

Open `/docs`, authorize with a candidate access token, then call
`GET /api/v1/jobs`, optionally with `search`, `limit` and `offset`.

For automated checks, set `RUN_DATABASE_INTEGRATION_TESTS=1` against an
isolated PostgreSQL 18.4 database and run `uv run python scripts/validate.py`.
