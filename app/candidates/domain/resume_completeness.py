"""Provisional résumé completeness rule shared by candidate and admin views."""


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
