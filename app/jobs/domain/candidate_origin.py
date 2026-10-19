from enum import StrEnum


class CandidateOrigin(StrEnum):
    """How a professional reached a company's job list (US-20).

    ``application`` means the professional applied to the job. ``automatic_match``
    means the platform found a compatible profile that has not applied. The origin
    never changes the compatibility percentage (US-19).
    """

    APPLICATION = "application"
    AUTOMATIC_MATCH = "automatic_match"
