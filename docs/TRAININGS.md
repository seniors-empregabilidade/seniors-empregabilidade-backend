# Training catalog (courses)

An administrator registers courses and relates them to skills and jobs.
Candidates see only published courses, searched by skill. Related jobs never
reach candidates.

## Candidate search

`GET /api/v1/trainings` requires any signed-in user (`401` when anonymous) and
lists published courses ordered by title, with `items` and `total`.

- `skill`: optional text; matches any catalog skill whose name contains it,
  ignoring case and accents. A text no skill name could contain returns an
  empty list without querying.
- `skill_id`: optional; matches one exact skill. With both, a course must match
  both. With neither, every published course is listed.
- `limit`: 1–50, default 20. `offset`: 0 or more.

Each item has `id`, `title`, `institution`, `mode`, `external_link` and
`skills`.

## Administration

Every route under `/api/v1/admin/trainings` requires `require_administrator`
(`401` anonymous, `403 administrator_required` otherwise).

| Endpoint | Result |
| --- | --- |
| `GET /admin/trainings` | `200`: every course, published or not, ordered by title. Filters: `search` (title or institution, up to 150 characters), `skill_id`, `published`, `limit` 1–50 (default 20), `offset` |
| `POST /admin/trainings` | `201`: creates a course |
| `GET /admin/trainings/{id}` | `200`, or `404 training_not_found` |
| `PATCH /admin/trainings/{id}` | `200`: changes only the fields sent; `404 training_not_found` |
| `DELETE /admin/trainings/{id}` | `204`: removes the course and its links to skills and jobs; `404 training_not_found` |

The body has `title` and `institution` (1–150 characters), `mode` (`onsite`,
`hybrid`, `remote`, `online`), `external_link` (an `http` or `https` URL up to
2048 characters, no whitespace), `published` (default `false`), and `skill_ids`
and `job_ids` (up to 50 each, repeats ignored). `skill_ids` and `job_ids` are
the complete set: on `PATCH` an empty list removes every relation of that kind.
A `PATCH` must send at least one field, and none of them as `null`. An unknown
skill or job answers `422 training_relation_not_found` on that field.

Responses carry `published`, `skills`, `job_ids` and `jobs` (`id`, `title`,
ordered by title).
