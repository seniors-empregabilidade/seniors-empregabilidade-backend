from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidates.exceptions import ProfessionalNotFoundError
from app.candidates.services.guidance_record import GuidanceRecord
from app.core.errors import ProblemException
from app.db.models import Administrator, Candidate, ResumeGuidance


def record_guidance(
    professional_id: UUID,
    administrator_id: UUID,
    note: str,
    *,
    session: Session,
) -> GuidanceRecord:
    try:
        professional = session.scalar(
            select(Candidate.id)
            .where(Candidate.id == professional_id)
            .with_for_update()
        )
        if professional is None:
            raise ProfessionalNotFoundError()

        administrator = session.get(Administrator, administrator_id)
        if administrator is None:
            raise ProblemException(
                status_code=403,
                title="Forbidden",
                code="administrator_required",
                detail="An administrator account is required.",
            )

        guidance = ResumeGuidance(
            candidate_id=professional_id,
            administrator_id=administrator_id,
            note=note,
        )
        session.add(guidance)
        session.flush()
        record = GuidanceRecord(
            id=guidance.id,
            note=guidance.note,
            created_at=guidance.created_at,
            administrator_name=administrator.full_name,
        )
        session.commit()
        return record
    except Exception:
        session.rollback()
        raise
