from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from psycopg.errors import CheckViolation, UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.candidates.domain.cpf import Cpf, InvalidCpfValueError
from app.candidates.domain.minimum_age import age_on, meets_minimum_age
from app.candidates.exceptions import (
    CpfAlreadyRegisteredError,
    EmailAlreadyRegisteredError,
    InvalidCpfError,
    MinimumAgeNotMetError,
    TermsAcceptanceRequiredError,
)
from app.candidates.schemas import ProfessionalRegistrationRequest
from app.core.errors import ProblemException
from app.db.models import AppUser, Candidate
from app.db.models.enums import UserType
from app.identity.exceptions import IdentityConflictError
from app.identity.provider import IdentityProvider


@dataclass(frozen=True, slots=True)
class RegisteredProfessional:
    id: UUID
    full_name: str
    email: str
    email_verification_required: bool


def register_professional(
    request: ProfessionalRegistrationRequest,
    *,
    session: Session,
    identity_provider: IdentityProvider,
    today: date | None = None,
    now: datetime | None = None,
) -> RegisteredProfessional:
    reference_date = today or date.today()
    accepted_at = now or datetime.now(UTC)

    try:
        cpf = Cpf.parse(request.cpf)
    except InvalidCpfValueError as exc:
        raise InvalidCpfError from exc

    if not meets_minimum_age(request.birth_date, reference_date):
        raise MinimumAgeNotMetError
    if request.terms_version_accepted is None:
        raise TermsAcceptanceRequiredError

    email = str(request.email).casefold()
    try:
        user = AppUser(
            email=email,
            identity_subject=None,
            user_type=UserType.CANDIDATE,
        )
        session.add(user)
        session.flush()

        candidate = Candidate(
            id=user.id,
            full_name=request.full_name,
            cpf=cpf.value,
            birth_date=request.birth_date,
            age=age_on(request.birth_date, reference_date),
            phone=request.phone,
            city=request.city,
            state=request.state,
            terms_version_accepted=request.terms_version_accepted,
            terms_accepted_at=accepted_at,
        )
        session.add(candidate)
        session.flush()

        identity = identity_provider.register(
            email=email,
            password=request.password.get_secret_value(),
        )
        user.identity_subject = identity.identity_subject
        session.flush()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise _translate_integrity_error(exc) from exc
    except IdentityConflictError as exc:
        session.rollback()
        raise EmailAlreadyRegisteredError from exc
    except Exception:
        session.rollback()
        raise

    return RegisteredProfessional(
        id=user.id,
        full_name=candidate.full_name,
        email=user.email,
        email_verification_required=not identity.confirmed,
    )


def _translate_integrity_error(error: IntegrityError) -> ProblemException:
    original = error.orig
    if isinstance(original, (UniqueViolation, CheckViolation)):
        constraint_name = original.diag.constraint_name
        if constraint_name == "uq_candidate_cpf":
            return CpfAlreadyRegisteredError()
        if constraint_name == "uq_app_user_email":
            return EmailAlreadyRegisteredError()
        if constraint_name in {
            "ck_candidate_age_value",
            "ck_candidate_minimum_age",
        }:
            return MinimumAgeNotMetError()
    raise error
