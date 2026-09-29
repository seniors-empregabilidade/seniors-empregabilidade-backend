from app.jobs.schemas.job import JobResponse


class JobSummaryResponse(JobResponse):
    application_count: int
