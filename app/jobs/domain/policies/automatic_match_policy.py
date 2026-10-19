"""Which compatible profiles a company sees without an application (US-20).

A professional who has not applied appears as an automatic match only when the
compatibility engine highlights them (50% or more of the required skills). The
threshold is the US-19 highlight, so "compatible" means the same thing in the
ranking and in the automatic matches. Applicants are always listed, whatever their
percentage; this rule only decides which non-applicants join them.
"""

from app.jobs.domain.value_objects.compatibility_score import CompatibilityScore


def is_automatic_match(score: CompatibilityScore) -> bool:
    return score.is_highlighted
