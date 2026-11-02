from uuid import UUID

from pydantic import BaseModel

from app.applications.schemas.applicant_certification_response import (
    ApplicantCertificationResponse,
)
from app.candidates.schemas.profile import EducationResponse, ExperienceResponse
from app.skills.schemas import SkillResponse


class ApplicantDetailResponse(BaseModel):
    application_id: UUID
    candidate_id: UUID
    full_name: str
    city: str | None
    state: str | None
    summary: str | None
    experiences: list[ExperienceResponse]
    education: list[EducationResponse]
    certifications: list[ApplicantCertificationResponse]
    skills: list[SkillResponse]
