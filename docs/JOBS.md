# Job publishing and "Minhas vagas" (US-17)

An approved company publishes a job and reads the jobs it published. Both
endpoints require `require_approved_company`: an anonymous request gets `401`,
and a candidate, an administrator or a company that is not approved gets `403
approved_company_required`.

## Endpoints

All paths start with `/api/v1`.

| Endpoint | Success |
| --- | --- |
| `POST /jobs` | `201`: the created job, already `published` |
| `GET /jobs/me` | `200`: every job of the calling company, newest first |

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

Both endpoints return the same job shape: `id`, `company_id`, `title`,
`description`, `skills` (`id`, `name`, `type`), `work_mode`, `closing_date`,
`status`, `published_at` (null for a job that was never published) and
`created_at`. `POST /jobs` returns the skills in the order they were sent,
without repeated names; `GET /jobs/me` sorts each job's skills by name, because
the typed order is not stored.

## Failures

| Status | `code` | When |
| --- | --- | --- |
| `422` | `validation_error` | A field is missing or invalid; `errors` is keyed by location, such as `body.title` or `body.skills.0.name` |
| `422` | `closing_date_in_the_past` | `closing_date` is before today; `errors` is keyed by `closing_date` |
| `500` | `internal_error` | Any unexpected failure, including a lost database connection |

## Transaction

Publishing resolves the skills, creates the job and links them in one
transaction. Any failure rolls all of it back, so a failed request leaves no
job, no job skill link and no skill created only for that job. The interface
treats a job as published only after a `201`.

A client that loses the response to a request the server did commit cannot
tell that it succeeded; retrying creates a second job. There is no idempotency
key yet.

## Known limits

- `GET /jobs/me` has no pagination or filters.
- `closing_date` is compared with the server's calendar date, not the
  `America/Sao_Paulo` date that `app.applications` uses, so late in the evening
  in Brazil a closing date of "today" can be rejected as past.
