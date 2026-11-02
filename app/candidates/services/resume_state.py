"""SQL predicates for the six fields in the US-08 completeness policy."""

from sqlalchemy import ColumnElement, and_, func, select

from app.db.models import Candidate, Education, Experience, Resume, ResumeSkill

# Match str.strip() in the US-08 policy, including Unicode whitespace.
_WHITESPACE = (
    " \t\n\r\v\f\x1c\x1d\x1e\x1f\u0085\u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)


def resume_section_presence() -> tuple[
    ColumnElement[bool], ColumnElement[bool], ColumnElement[bool]
]:
    return (
        select(Experience.id).where(Experience.resume_id == Resume.id).exists(),
        select(Education.id).where(Education.resume_id == Resume.id).exists(),
        select(ResumeSkill.skill_id).where(ResumeSkill.resume_id == Resume.id).exists(),
    )


def resume_is_complete() -> ColumnElement[bool]:
    return and_(
        func.length(func.btrim(func.coalesce(Candidate.city, ""), _WHITESPACE)) > 0,
        func.length(func.btrim(func.coalesce(Candidate.state, ""), _WHITESPACE)) > 0,
        func.length(func.btrim(func.coalesce(Resume.summary, ""), _WHITESPACE)) > 0,
        *resume_section_presence(),
    )
