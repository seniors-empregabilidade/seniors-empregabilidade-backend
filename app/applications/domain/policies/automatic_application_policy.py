"""Whether the platform applies to a job on a professional's behalf.

The platform applies only when the professional's compatibility with the job
reaches the configured threshold (70% by default). The comparison uses the exact
ratio, like the US-19 highlight, so rounding never lifts 69.995% to the threshold.
"""

from app.jobs.domain.value_objects.compatibility_score import CompatibilityScore


def qualifies_for_automatic_application(
    score: CompatibilityScore, threshold_percent: int
) -> bool:
    return score.matched_count * 100 >= threshold_percent * score.required_count
