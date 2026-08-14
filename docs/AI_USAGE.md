# AI usage policy

AI-assisted development is permitted and expected to be handled transparently. This policy applies to coding assistants, chat systems, completion tools, and agentic tools.

## Allowed uses

AI may assist with exploration, explanations, implementation drafts, tests, documentation, refactoring, debugging, and review. Its output is a proposal until a human contributor inspects, understands, adapts, and validates it.

## Human responsibility

The human contributor remains the sole author and owner of the submitted change. They must be able to explain the design and code, verify that it matches confirmed scope, review the complete diff, and run the validation reported in the pull request.

AI output cannot approve itself, replace review by another person, or satisfy the required AGES III/IV approval. Do not add AI tools as commit co-authors, and do not add `Co-authored-by` trailers.

## Data protection

Never send secrets, credentials, tokens, database URLs, personal information, résumés, certificates, production data, private stakeholder material, logs containing identifiers, or identifiable user content to an AI tool. Use synthetic or anonymized examples. If uncertain whether material is sensitive, do not provide it.

## Disclosure

For material assistance, select the AI-assistance option in the pull request template and identify:

- the tool or tools used;
- the areas assisted;
- the human validation performed.

Publishing complete prompts or transcripts is not required. Minor editor completion does not need separate disclosure unless it materially shaped the change.

## Guardrails

AI tools must follow `AGENTS.md`, repository hooks, branch protection, dependency policy, scope constraints, database safety, and privacy requirements. They must not use `--no-verify`, weaken checks, invent requirements, create speculative entities, commit or publish without explicit authorization, or overwrite unrelated human work.
