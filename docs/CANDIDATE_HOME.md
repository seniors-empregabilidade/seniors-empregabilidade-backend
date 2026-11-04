# Candidate home summary (US-32-T01)

The candidate home page shows three cards: résumé completeness, the three most
recent applications and three open jobs. The card asks for no new matching or
completeness calculation, and each card must load and fail on its own while the
others stay visible. So the backend does not add an aggregate endpoint: each
card reads the endpoint that already owns its data, and this task only fills
the two gaps those endpoints had.

| Card | Request | Source rule |
| --- | --- | --- |
| Greeting and profile | `GET /api/v1/professionals/me` | US-08 missing-field policy ([RESUME_ASSISTANCE.md](RESUME_ASSISTANCE.md)) |
| Recent applications | `GET /api/v1/applications/me?limit=3` | US-13 listing ([APPLICATIONS.md](APPLICATIONS.md)) |
| Opportunities | `GET /api/v1/jobs?limit=3` | US-10 search and compatibility ([JOB_SEARCH.md](JOB_SEARCH.md)) |

All three require `require_candidate` (`401 invalid_access_token` without a
token, `403 candidate_required` for companies and administrators), read only
the caller's own data, and answer with `Cache-Control: no-store`, so returning
to the page after editing the profile, applying or receiving a status change
shows the current state.

## What this task added

- **`completion_percentage` on the profile.** `GET` and `PATCH
  /api/v1/professionals/me` now return an integer from 0 to 100: the share of
  the six US-08 fields (`city`, `state`, `summary`, `experiences`,
  `education`, `skills`) that are filled in, each weighing the same, rounded
  half up (0, 17, 33, 50, 67, 83, 100). It is computed from `missing_fields`
  by `app/candidates/domain/resume_completeness.py::resume_completion_percentage`,
  so it is 100 exactly when `missing_fields` is empty and the card never shows
  a pending item the profile does not have. It does not read the legacy
  `resume.completion_percentage` column, which profile edits do not maintain.
- **`limit` on `GET /api/v1/applications/me`.** Optional, from 1 to 100. It
  keeps the first applications of the existing order (submission date, most
  recent first). Without it every application is returned, as before. It
  combines with `company_name`; out-of-range values return `422
  validation_error` under `errors.query.limit`.

The opportunities card needs nothing new: `GET /api/v1/jobs` with `limit=3` and
no `search` returns the open jobs ordered by the US-10 compatibility, with
company, location, work mode, optional salary ceiling, matched and required
skill counts and missing skills. It is not a recommendation engine.

## Known gaps

- The percentage inherits the provisional status of the US-08 rule: when the
  team settles the definition of a complete résumé, both `missing_fields` and
  `completion_percentage` change together.
- The applications endpoint has no `offset`; the "Ver todas" link opens the
  full listing, which is unpaginated as before.
