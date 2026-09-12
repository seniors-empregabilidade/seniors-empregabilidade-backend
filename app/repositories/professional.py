from sqlalchemy.orm import Session
from app.models.professional import Professional


def exists_by_cpf(session: Session, cpf: str) -> bool:
    return session.query(Professional).filter(Professional.cpf == cpf).first() is not None


def exists_by_email(session: Session, email: str) -> bool:
    return session.query(Professional).filter(Professional.email == email).first() is not None


def create(session: Session, professional: Professional) -> Professional:
    session.add(professional)
    session.flush()  # assign id
    return professional
