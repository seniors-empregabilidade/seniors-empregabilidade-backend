from dataclasses import dataclass

from app.jobs.services.job_record import JobRecord


@dataclass(frozen=True, slots=True)
class JobSummary:
    """A job as its company lists it, with how many applications it received."""

    record: JobRecord
    application_count: int
