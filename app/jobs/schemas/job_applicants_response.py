from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import ApplicationStatus


class ApplicantProfileResponse(BaseModel):
    candidate_id: UUID
    full_name: str
    city: str | None
    state: str | None


class JobApplicantResponse(BaseModel):
    application_id: UUID
    status: ApplicationStatus
    match_score: int | None
    matched_skill_count: int
    required_skill_count: int
    profile: ApplicantProfileResponse


class JobApplicantsSummaryResponse(BaseModel):
    job_id: UUID
    total_applicant_count: int
    full_match_count: int
    applicants: list[JobApplicantResponse]
