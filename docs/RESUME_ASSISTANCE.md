# Résumé assistance (US-08-T01)

This backend contract supports the administrator résumé assistance screen from
[frontend PR #73](https://github.com/seniors-empregabilidade/seniors-empregabilidade-frontend/pull/73).
The same completeness policy supplies the candidate's pending fields and the
administrator's filters. All responses containing personal information or
guidance use `Cache-Control: no-store`.

## Candidate view

`GET /api/v1/professionals/me` requires a candidate and includes
`missing_fields`, an ordered array of field keys. It does not return guidance
notes or contact status. The existing profile response fields remain available.

## Administrator list

`GET /api/v1/professionals` requires an administrator and returns a JSON array.
Each item has `id`, `full_name`, `email`, `phone`, nullable `city` and `state`,
`missing_fields`, and nullable `last_guidance`. The last guidance object has
`id`, `note`, `created_at`, and `administrator_name`.

| Query parameter | Values | Default |
| --- | --- | --- |
| `completeness` | `complete`, `incomplete` | All professionals |
| `contact_status` | `contacted`, `not_contacted` | All professionals |
| `limit` | Integer from 1 to 100 | 50 |
| `offset` | Nonnegative integer | 0 |

The filters can be combined. A professional is `contacted` after at least one
guidance entry has been saved. Results are ordered by `full_name`, then `id`;
filters are applied before pagination. An empty page is an empty array. The
response has no total count.

## Guidance history

`POST /api/v1/professionals/{professional_id}/guidance` requires an
administrator. The JSON body is `{ "note": "..." }`; surrounding whitespace is
removed and the resulting note must contain 1 to 2000 characters. Additional
request fields are rejected. A successful request appends a guidance entry and
returns its `id`, trimmed `note`, server-generated `created_at`, and
`administrator_name` with HTTP 201. The administrator identity comes from the
authenticated account. The list returns only the latest entry for each
professional; older entries remain stored.

An unknown professional returns `404 professional_not_found`. Invalid input or
query parameters return `422 validation_error`. Authentication and role errors
use the existing `401` and `403` problem responses. Error bodies use
`application/problem+json`.

## Provisional completeness rule

`missing_fields` contains these keys in order when their value is absent:
`city`, `state`, `summary`, `experiences`, `education`, `skills`. City, state,
and summary count as present when they contain non-whitespace text. Each
collection counts as present when it has at least one item. A résumé is
`complete` when `missing_fields` is empty. Certifications and documents do not
affect this rule. The existing `completion_percentage` persistence column does
not define this status and is not returned by these endpoints.

**TODO (team decision):** The team has not finalized the full definition of a
complete résumé, including any required details within each collection or a
numeric completion percentage. Review this provisional rule with the team
before treating it as a settled product policy.
