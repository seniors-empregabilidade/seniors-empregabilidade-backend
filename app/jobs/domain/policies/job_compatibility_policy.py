"""Compatibility between a job and candidates.

Rules:

1. A candidate matches a required skill when both point at the same catalog skill id.
   Repeated ids on either side count once.
2. percentage = matched required skills / required skills * 100, rounded half up to
   two decimal places. Skills the candidate has beyond the job's do not count.
3. A job must require at least one skill (US-17 already enforces 1 to 100), so an
   empty requirement raises ``JobWithoutRequiredSkillsError`` instead of a score.
4. A candidate is highlighted at 50% or more, compared on the exact ratio.
   Candidates below 50% stay in the ranking.
5. Ranking: percentage descending, then ``candidate_id`` ascending, so the same input
   always produces the same order.
"""

from collections.abc import Iterable, Mapping
from uuid import UUID

from app.jobs.domain.exceptions import JobWithoutRequiredSkillsError
from app.jobs.domain.value_objects.compatibility_score import CompatibilityScore


class JobCompatibilityPolicy:
    def __init__(self, required_skill_ids: Iterable[UUID]) -> None:
        self._required_skill_ids = frozenset(required_skill_ids)
        if not self._required_skill_ids:
            raise JobWithoutRequiredSkillsError

    def score(
        self, candidate_id: UUID, candidate_skill_ids: Iterable[UUID]
    ) -> CompatibilityScore:
        matched = self._required_skill_ids & frozenset(candidate_skill_ids)
        return CompatibilityScore(
            candidate_id=candidate_id,
            matched_skill_ids=matched,
            missing_skill_ids=self._required_skill_ids - matched,
        )

    def rank(
        self, skill_ids_by_candidate: Mapping[UUID, Iterable[UUID]]
    ) -> list[CompatibilityScore]:
        scores = [
            self.score(candidate_id, skill_ids)
            for candidate_id, skill_ids in skill_ids_by_candidate.items()
        ]
        return sorted(scores, key=lambda score: (-score.percentage, score.candidate_id))
