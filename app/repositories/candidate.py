from sqlalchemy.orm import Session

from app.db.models.candidate import Candidate


def exists_by_cpf(session: Session, cpf: str) -> bool:
    return session.query(Candidate).filter(Candidate.cpf == cpf).first() is not None


def exists_by_email(session: Session, email: str) -> bool:
    return session.query(Candidate).filter(Candidate.email == email).first() is not None


def create(session: Session, candidate: Candidate) -> Candidate:
    session.add(candidate)
    session.flush()  # assign id
    return candidate
