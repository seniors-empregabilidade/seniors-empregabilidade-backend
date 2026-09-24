from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RequirementMatch:
    """How many of a job's required skills a candidate's resume covers.

    `total` is the number of distinct skills the job requires; `matched` is how
    many of those the candidate's resume also lists. `total == 0` means the job
    lists no structured skill requirement, so `matched` is also `0` and the
    candidate trivially satisfies every (zero) requirement.
    """

    matched: int
    total: int


def match_requirements(
    *,
    required_skill_ids: Iterable[UUID],
    candidate_skill_ids: Iterable[UUID],
) -> RequirementMatch:
    """Compare a job's required skills against a candidate's resume skills.

    Provisional US-10 stand-in: there is no shared compatibility/matching engine
    yet, so this counts a plain set intersection between the two skill-id
    collections, giving every skill equal weight regardless of type (hard/soft)
    or how central it is to the job. Replace this function's body with the
    real engine once it exists; callers only depend on `RequirementMatch`.
    """
    required = set(required_skill_ids)
    matched = len(required & set(candidate_skill_ids))
    return RequirementMatch(matched=matched, total=len(required))
