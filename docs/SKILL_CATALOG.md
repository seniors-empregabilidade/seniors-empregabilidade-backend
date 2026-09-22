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

The normalization lives in `app.skills.domain.SkillName`, and
`app.skills.services.find_or_create_skills` is the only place that creates a
skill. The database enforces the rest: `uq_skill_normalized_name` rejects a
duplicate even when two requests arrive at the same time.

## API contract

All paths start with `/api/v1`. Any authenticated account may read the catalog.

| Endpoint | Request | Success |
| --- | --- | --- |
| `GET /skills` | `search` (optional, matched without case or accents), `limit` (1–50, default 20) | `200`: list of `id`, `name`, `type`, sorted by name |

Requests that create or attach skills send objects, not identifiers:

```json
{ "skills": [{ "name": "NR-11", "type": "hard" }] }
```

Responses return the resolved catalog entries, so an interface can render the
stored spelling and send the `id` back later:

```json
{ "skills": [{ "id": "…", "name": "NR-11", "type": "hard" }] }
```

## Remaining work

Course skills, résumé skill editing and the compatibility calculation consume this
catalog and are implemented by their own user stories. Merging or renaming catalog
entries has no administrative endpoint yet.
