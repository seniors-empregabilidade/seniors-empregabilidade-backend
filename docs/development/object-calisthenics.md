# Readable code constraints

Object Calisthenics is used here as a review heuristic, not as a reason to obscure
simple Python. Favor code that makes invariants, side effects, and failure paths
obvious.

## Guidelines

- Prefer guard clauses and early returns over nested `else` branches.
- Keep one conceptual level of abstraction per function.
- Extract complex conditions into named domain questions or policies.
- Use complete names; avoid unexplained abbreviations.
- Keep transactions and external calls visible in the application operation.
- Avoid mutable global state and hidden side effects.
- Prefer small immutable values and explicit inputs.
- Do not chain through deep object graphs; ask the owning object a meaningful
  question.
- Split a file when it owns multiple principal concepts.
- Add comments only for non-obvious constraints or intentional deviations.

Do not mechanically enforce arbitrary line counts, one-dot expressions, or wrapper
classes. Ruff formatting, strict mypy, tests, and human readability remain the
objective checks.
