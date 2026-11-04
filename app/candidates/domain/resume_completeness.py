"""Provisional résumé completeness rule shared by candidate and admin views."""

RESUME_FIELDS = ("city", "state", "summary", "experiences", "education", "skills")


def missing_resume_fields(
    *,
    city: str | None,
    state: str | None,
    summary: str | None,
    has_experience: bool,
    has_education: bool,
    has_skill: bool,
) -> tuple[str, ...]:
    missing: list[str] = []
    if not city or not city.strip():
        missing.append("city")
    if not state or not state.strip():
        missing.append("state")
    if not summary or not summary.strip():
        missing.append("summary")
    if not has_experience:
        missing.append("experiences")
    if not has_education:
        missing.append("education")
    if not has_skill:
        missing.append("skills")
    return tuple(missing)


def resume_completion_percentage(missing_fields: tuple[str, ...]) -> int:
    """Share of `RESUME_FIELDS` filled in, from 0 to 100, rounded half up.

    It is derived from the same missing-field rule, so 100 means exactly that
    `missing_fields` is empty. Each field weighs the same.
    """
    filled = len(RESUME_FIELDS) - len(missing_fields)
    return (filled * 200 + len(RESUME_FIELDS)) // (2 * len(RESUME_FIELDS))
