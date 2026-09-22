from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidates.exceptions import ProfileNotFoundError
from app.db.models.candidate import Candidate
from app.db.models.resume import Resume


def get_or_create_resume(user_id: UUID, session: Session) -> Resume:
    if session.get(Candidate, user_id) is None:
        raise ProfileNotFoundError()
    resume = session.scalar(select(Resume).where(Resume.candidate_id == user_id))
    if resume is None:
        resume = Resume(candidate_id=user_id)
        session.add(resume)
        session.flush()
    return resume
