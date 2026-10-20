# Skill catalog

Compatibility between a job and a résumé is a comparison of skill rows, so both
sides must point at the same catalog entry. The catalog is a single `skill` table
read through suggestions while a person types.

## Who types and who chooses

| Actor | Behavior |
| --- | --- |
| Company publishing a job | Types freely; an unknown name creates a catalog skill |
| Administrator registering a course | Same as the company |
| Candidate editing the résumé | Chooses an existing catalog skill; typing only filters suggestions |

A created skill needs its type (`hard` for a technical skill, `soft` for a
behavioral one) because the catalog classifies every entry. The type is ignored
when the name already exists: the stored classification wins.

## Identity of a skill

`skill.normalized_name` holds the name without surrounding or repeated spaces,
without letter case, accents (including an accent typed on its own, such as "´")
and invisible characters, and it is unique. So "Gestão de equipes",
"gestao de equipes" and " GESTÃO  DE EQUIPES " are one catalog entry, while
`skill.name` keeps the first spelling that created it and is what the interface
shows.

Both columns hold at most 100 characters. Case folding can lengthen a name ("ß"
becomes "ss"), so a name is rejected with `422 validation_error` when its
normalized form exceeds 100 characters or has nothing visible left, as in a name
made only of accents, or when it carries a control character such as NUL.

A search follows the same normalization. A blank search lists the catalog, and a
search that no stored name could contain returns an empty list.

The normalization lives in `app.skills.domain.SkillName`. Runtime creation uses
`app.skills.services.find_or_create_skills`. Migration `753757edc4f5` adds
"Ética" and "Trabalho em grupo" as baseline soft skills because
`scripts/seed.py` runs only in local and test environments. The database enforces
the rest: `uq_skill_normalized_name` rejects a duplicate even when two requests
arrive at the same time. The migration preserves pre-existing entries and its
downgrade leaves both names in the catalog because their origin is unknown.

## API contract

All paths start with `/api/v1`. Any authenticated account may read the catalog.

| Endpoint | Request | Success |
| --- | --- | --- |
| `GET /skills` | `search` (optional, matched without case or accents), `limit` (1–50, default 20) | `200`: list of `id`, `name`, `type`, sorted by name |
| `PUT /professionals/me/skills` | `{ "skill_ids": ["<uuid>"] }` (up to 100 catalog IDs; an empty list clears the selection) | `200`: final list of `id`, `name`, `type`, sorted by name |

Companies and administrators creating skills send objects:

```json
{ "skills": [{ "name": "NR-11", "type": "hard" }] }
```

Candidates select existing catalog entries by `id` through
`PUT /professionals/me/skills`; names and free text are rejected with
`422 validation_error`. An unknown `id` returns `404 skill_not_found` without
changing the selection. The PUT response is a list of resolved catalog entries,
so an interface can render the stored spelling:

```json
[{ "id": "<uuid>", "name": "NR-11", "type": "hard" }]
```

## Remaining work

Course skills and the compatibility calculation consume this catalog and are
implemented by their own user stories. Merging or renaming catalog entries has no
administrative endpoint yet.
