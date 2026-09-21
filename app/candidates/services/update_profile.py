from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidates.exceptions import ProfileNotFoundError
from app.candidates.schemas.profile import (
    ProfessionalProfileResponse,
    ProfessionalProfileUpdateRequest,
)
from app.candidates.services.get_profile import get_profile
from app.db.models.candidate import Candidate
from app.db.models.resume import Resume


def update_profile(
    user_id: UUID,
    request: ProfessionalProfileUpdateRequest,
    *,
    session: Session,
) -> ProfessionalProfileResponse:
    try:
        candidate = session.get(Candidate, user_id)
        if candidate is None:
            raise ProfileNotFoundError()

        changes = request.model_dump(exclude_unset=True)

        if "full_name" in changes:
            candidate.full_name = changes["full_name"]
        if "phone" in changes:
            candidate.phone = changes["phone"]
        if "city" in changes:
            candidate.city = changes["city"]
        if "state" in changes:
            candidate.state = changes["state"]

        if "summary" in changes:
            resume = session.scalar(
                select(Resume).where(Resume.candidate_id == user_id)
            )
            if resume is None:
                resume = Resume(candidate_id=user_id)
                session.add(resume)
            resume.summary = changes["summary"]

        session.flush()
        profile = get_profile(user_id, session=session)
        session.commit()
        return profile
    except Exception:
        session.rollback()
        raise
