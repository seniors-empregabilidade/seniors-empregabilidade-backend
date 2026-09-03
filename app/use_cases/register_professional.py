from datetime import date
from typing import List, Dict

from sqlalchemy.orm import Session

from app.core.cpf import validate_cpf
from app.core.errors import ProblemException
from app.core.passwords import hash_password
from app.models.professional import Professional
from app.repositories.professional import exists_by_cpf, exists_by_email, create
from app.schemas.professional import ProfessionalCreateRequest


def _calculate_age(born: date) -> int:
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def register_professional(request: ProfessionalCreateRequest, session: Session) -> int:
    """Validate and register a professional.

    Returns the newly created professional ``id``.
    Raises ``ProblemException`` with a structured ``errors`` dict on validation failures.
    """
    errors: Dict[str, List[Dict[str, str]]] = {}

    # CPF validation
    if not validate_cpf(request.cpf):
        errors.setdefault("cpf", []).append({"code": "invalid_cpf", "message": "CPF inválido"})
    # Age validation (must be >= 45 years)
    if _calculate_age(request.date_of_birth) < 45:
        errors.setdefault("date_of_birth", []).append({"code": "underage", "message": "O profissional deve ter ao menos 45 anos"})

    # Password validation (length + complexity)
    if len(request.password) < 8:
        errors.setdefault("password", []).append({"code": "password_too_short", "message": "Senha deve ter no mínimo 8 caracteres"})
    else:
        import re
        pattern = r'(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9])'
        if not re.search(pattern, request.password):
            errors.setdefault("password", []).append({"code": "password_complexity", "message": "Senha deve conter letra maiúscula, minúscula, número e símbolo"})
    # Duplicate checks
    if exists_by_cpf(session, request.cpf):
        errors.setdefault("cpf", []).append({"code": "duplicate_cpf", "message": "CPF já cadastrado"})
    if exists_by_email(session, request.email):
        errors.setdefault("email", []).append({"code": "duplicate_email", "message": "E‑mail já cadastrado"})

    if errors:
        raise ProblemException(
            status_code=400,
            title="Validation Error",
            code="validation_error",
            detail="The request contains invalid data.",
            errors=errors,
        )

    # All validations passed – create the professional
    hashed = hash_password(request.password)
    professional = Professional(
        full_name=request.full_name,
        cpf=request.cpf,
        date_of_birth=request.date_of_birth,
        email=request.email,
        hashed_password=hashed,
    )
    created = create(session, professional)
    session.commit()
    return created.id
