from collections.abc import Set
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SkillMatch:
    matched_count: int
    required_count: int
    missing_skill_ids: frozenset[UUID]


def match_skills(
    *, candidate_skill_ids: Set[UUID], required_skill_ids: Set[UUID]
) -> SkillMatch:
    """Compare a candidate's catalog skills with the ones a job requires."""
    return SkillMatch(
        matched_count=len(required_skill_ids & candidate_skill_ids),
        required_count=len(required_skill_ids),
        missing_skill_ids=frozenset(required_skill_ids - candidate_skill_ids),
    )
