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
