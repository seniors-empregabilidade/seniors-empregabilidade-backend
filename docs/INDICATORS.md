# Platform indicators

`GET /api/v1/indicators` aggregates platform indicators for administrators
(CU-86e3ke4qv, US-24-T01). The endpoint requires an administrator account and
answers with `Cache-Control: no-store`.

## Filters

All filters are optional query parameters and combine with AND.

| Parameter | Type | Applies to |
|---|---|---|
| `start_date` | date | Every indicator. First day of the period, inclusive. |
| `end_date` | date | Every indicator. Last day of the period, inclusive. |
| `account_status` | `AccountStatus` | Candidate/company accounts, candidate segments and matches. |
| `candidate_availability` | `AvailabilityStatus` | Candidates, candidate segments and matches. |
| `company_status` | `CompanyStatus` | Companies and matches. |
| `job_status` | `JobStatus` | Jobs and matches. |
| `application_status` | `ApplicationStatus` | Applications only. |

A status filter restricts its own entity count and, when applicable, potential
matches. Filtering by `company_status` does not change the job count.
Potential matches do not require an application, so `application_status` never
changes them.

`start_date` after `end_date` fails with `422` and the stable code
`invalid_period`. Unknown status values fail with the standard validation
error.

## Period semantics

The period includes complete calendar days in `America/Sao_Paulo`, using the
shared product timezone. Both bounds are inclusive, from `00:00:00` through
`23:59:59.999999`. Omitting one bound leaves that side open. The maximum ISO
date `9999-12-31` works without adding a day or overflowing.
Every entity is dated by the moment it was registered on the platform:

| Entity | Reference date |
|---|---|
| Candidate | `app_user.created_at` of the candidate's account |
| Company | `app_user.created_at` of the company's account |
| Job | `job.created_at` |
| Application | `application.created_at` |

## Totals

| Field | Rule |
|---|---|
| `candidates` | Rows of `candidate` matching the filters. |
| `companies` | Rows of `company` matching the filters, in any status unless filtered. |
| `jobs` | Rows of `job` matching the filters, drafts included unless filtered. |
| `applications` | Rows of `application` matching the filters. |
| `matches` | Distinct eligible candidate/job pairs with at least 50% compatibility. |

Entity counts include all account statuses unless `account_status` is supplied.
Potential matches always require active candidate and company accounts.

### Potential matches

A job must be published, owned by an approved and active company, and still
open on the current Brazil calendar day. The candidate account must be active.
The candidate's current catalog skills must cover at least 50% of the job's
requirements, using the exact-ratio US-19 threshold
(`HIGHLIGHT_THRESHOLD_PERCENT`), without rounding into eligibility.

Jobs without requirements produce no matches. Applications and their stored
historical scores are irrelevant. A candidate may match several jobs; each pair
is counted once through a grouped SQL intersection rather than a Cartesian
product loaded into Python or one query per profile.

Date filters apply to both candidate account and job creation dates. Account,
availability, company and job filters additionally restrict the pair. Selecting
blocked accounts, pending companies or closed jobs therefore yields no matches.
These are current-state counts for the selected creation cohorts, not a
reconstruction of historical statuses.

## Segments

All segments count candidates and respect the period, `account_status` and
`candidate_availability`.

| Field | Rule |
|---|---|
| `candidates_without_placement` | Candidates whose current `resume.employment_status` is `unemployed`. |
| `candidates_with_unknown_employment` | Candidates without a resume or with null employment status. |
| `incomplete_resumes` | Candidates missing any US-08 completeness field. |

Employment status is never inferred from application or hiring history.
Completeness follows the US-08 policy: nonblank city, state and summary, plus
at least one experience, education and skill. Whitespace handling agrees with
Python `str.strip()`, including Unicode whitespace. A missing resume is
incomplete. The legacy `completion_percentage` does not determine this metric.

## Response

```json
{
  "filters": {
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "account_status": null,
    "candidate_availability": null,
    "company_status": null,
    "job_status": null,
    "application_status": null
  },
  "totals": {
    "candidates": 0,
    "companies": 0,
    "jobs": 0,
    "applications": 0,
    "matches": 0
  },
  "segments": {
    "candidates_without_placement": 0,
    "candidates_with_unknown_employment": 0,
    "incomplete_resumes": 0
  }
}
```

`filters` echoes what was applied, so a consumer can tell an unfiltered answer
from a filtered one.

## Tests

`tests/indicators/test_platform_indicators.py` runs against PostgreSQL and needs
`RUN_DATABASE_INTEGRATION_TESTS=1`. It builds its data in January 2001 and
asserts exact counts for that window, so it assumes the database holds no
records created in that month.

`tests/indicators/test_indicator_integration.py` verifies real authorization,
live pairs without applications, exact compatibility boundaries, account
blocking/reactivation and audit, current employment, US-08 consistency despite
stale percentages, Brazil day boundaries and the maximum ISO date. Use an
isolated PostgreSQL test database for the full suite.

The dashboard consumes this contract at `/administrador`.
`GET /api/v1/indicators/export` downloads the same numbers, with the applied
filters, as a CSV file; see [EXPORTS.md](EXPORTS.md). No schema migration or
dependency is required.
