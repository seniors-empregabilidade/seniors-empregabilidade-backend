from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from app.jobs.domain.exceptions import JobWithoutRequiredSkillsError

HIGHLIGHT_THRESHOLD_PERCENT = 50
_HUNDRED = Decimal(100)
_TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class CompatibilityScore:
    """How well one candidate's skills cover the skills a job requires.

    Skills are compared by catalog id (``skill.id``), so the comparison inherits the
    catalog normalization: "Gestão de equipes" and "gestao de equipes" are one skill.
    """

    candidate_id: UUID
    matched_skill_ids: frozenset[UUID]
    missing_skill_ids: frozenset[UUID]

    def __post_init__(self) -> None:
        if not self.matched_skill_ids and not self.missing_skill_ids:
            raise JobWithoutRequiredSkillsError
        if self.matched_skill_ids & self.missing_skill_ids:
            raise ValueError("a skill cannot be both matched and missing")

    @property
    def required_count(self) -> int:
        return len(self.matched_skill_ids) + len(self.missing_skill_ids)

    @property
    def matched_count(self) -> int:
        return len(self.matched_skill_ids)

    @property
    def percentage(self) -> Decimal:
        """Matched / required * 100, rounded half up to two decimal places."""
        ratio = Decimal(self.matched_count) / Decimal(self.required_count)
        return (ratio * _HUNDRED).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

    @property
    def is_highlighted(self) -> bool:
        """Compares the exact ratio, so rounding never lifts 49.995% to a highlight."""
        return (
            self.matched_count * 100
            >= HIGHLIGHT_THRESHOLD_PERCENT * self.required_count
        )
