from datetime import date

from sqlalchemy.orm import Session
import re
import app.repositories.candidate as candidate_repo
from app.core.cpf import validate_cpf
from app.core.errors import ProblemException
from app.db.models.candidate import Candidate


def _calculate_age(born: date) -> int:
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def register_candidate(request, session: Session) -> str:
    """Validate input and register a candidate.

    Returns the newly created candidate ID as a string.
    Raises ProblemException with a structured errors dict on validation failures.
    """
    errors: dict[str, list[str]] = {}

    # CPF validation (sanitize and check)
    sanitized_cpf = re.sub(r"\D", "", request.cpf)
    if not validate_cpf(sanitized_cpf):
        errors.setdefault("cpf", []).append("CPF inválido")

    # Age validation (must be >= 45 years)
    if _calculate_age(request.date_of_birth) < 45:
        errors.setdefault("date_of_birth", []).append(
            "Idade mínima de 45 anos necessária"
        )

    # Password validation (length + complexity)
    if len(request.password) < 8:
        errors.setdefault("password", []).append(
            "A senha deve ter pelo menos 8 caracteres"
        )
    else:
        pattern = r"(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9])"
        if not re.search(pattern, request.password):
            errors.setdefault("password", []).append(
                "Senha deve conter letra maiúscula, minúscula, número e símbolo"
            )

    # If any basic validation errors, raise 400 before DB checks
    if errors:
        raise ProblemException(
            status_code=400,
            title="Validation Error",
            code="validation_error",
            detail="The request contains invalid data.",
            errors=errors,
        )

    # Duplicate checks (after basic validation passed)
    if candidate_repo.exists_by_cpf(session, sanitized_cpf):
        errors.setdefault("cpf", []).append("CPF já cadastrado")
    if candidate_repo.exists_by_email(session, request.email):
        errors.setdefault("email", []).append("E‑mail já cadastrado")

    if errors:
        raise ProblemException(
            status_code=409,
            title="Validation Error",
            code="validation_error",
            detail="The request contains invalid data.",
            errors=errors,
        )

    # All validations passed – create the candidate
    candidate = Candidate(
        full_name=request.full_name,
        cpf=sanitized_cpf,
        birth_date=request.date_of_birth,
        email=request.email,
        phone=request.phone,
    )
    created = candidate_repo.create(session, candidate)
    return str(created.id)
