from dataclasses import replace
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidates.domain.resume_completeness import missing_resume_fields
from app.candidates.services.guidance_record import GuidanceRecord
from app.candidates.services.professional_summary import ProfessionalSummary
from app.db.models import (
    Administrator,
    AppUser,
    Candidate,
    Education,
    Experience,
    Resume,
    ResumeGuidance,
    ResumeSkill,
)
from app.db.models.enums import UserType

CompletenessFilter = Literal["complete", "incomplete"]
ContactFilter = Literal["contacted", "not_contacted"]


def list_professionals(
    *,
    session: Session,
    completeness: CompletenessFilter | None,
    contact_status: ContactFilter | None,
    limit: int,
    offset: int,
) -> list[ProfessionalSummary]:
    has_experience = (
        select(Experience.id).where(Experience.resume_id == Resume.id).exists()
    )
    has_education = (
        select(Education.id).where(Education.resume_id == Resume.id).exists()
    )
    has_skill = (
        select(ResumeSkill.skill_id).where(ResumeSkill.resume_id == Resume.id).exists()
    )
    has_guidance = (
        select(ResumeGuidance.id)
        .where(ResumeGuidance.candidate_id == Candidate.id)
        .exists()
    )

    candidates = session.execute(
        select(
            Candidate.id,
            Candidate.full_name,
            AppUser.email,
            Candidate.phone,
            Candidate.city,
            Candidate.state,
            Resume.summary,
            has_experience,
            has_education,
            has_skill,
            has_guidance,
        )
        .join(AppUser, AppUser.id == Candidate.id)
        .outerjoin(Resume, Resume.candidate_id == Candidate.id)
        .where(AppUser.user_type == UserType.CANDIDATE)
        .order_by(Candidate.full_name, Candidate.id)
    ).all()

    selected: list[ProfessionalSummary] = []
    for row in candidates:
        (
            professional_id,
            full_name,
            email,
            phone,
            city,
            state,
            summary,
            experience_present,
            education_present,
            skill_present,
            guidance_present,
        ) = row
        missing = missing_resume_fields(
            city=city,
            state=state,
            summary=summary,
            has_experience=experience_present,
            has_education=education_present,
            has_skill=skill_present,
        )
        if completeness == "complete" and missing:
            continue
        if completeness == "incomplete" and not missing:
            continue
        if contact_status == "contacted" and not guidance_present:
            continue
        if contact_status == "not_contacted" and guidance_present:
            continue
        selected.append(
            ProfessionalSummary(
                id=professional_id,
                full_name=full_name,
                email=email,
                phone=phone,
                city=city,
                state=state,
                missing_fields=missing,
                last_guidance=None,
            )
        )

    page = selected[offset : offset + limit]
    if not page:
        return []

    professional_ids = [entry.id for entry in page]
    latest_guidance = {
        guidance.candidate_id: GuidanceRecord(
            id=guidance.id,
            note=guidance.note,
            created_at=guidance.created_at,
            administrator_name=administrator_name,
        )
        for guidance, administrator_name in session.execute(
            select(ResumeGuidance, Administrator.full_name)
            .join(Administrator, Administrator.id == ResumeGuidance.administrator_id)
            .where(ResumeGuidance.candidate_id.in_(professional_ids))
            .order_by(
                ResumeGuidance.candidate_id,
                ResumeGuidance.created_at.desc(),
                ResumeGuidance.id.desc(),
            )
            .distinct(ResumeGuidance.candidate_id)
        ).tuples()
    }

    return [replace(item, last_guidance=latest_guidance.get(item.id)) for item in page]
