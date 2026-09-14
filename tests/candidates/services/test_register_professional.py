from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.candidates.exceptions import (
    CpfAlreadyRegisteredError,
    EmailAlreadyRegisteredError,
    InvalidCpfError,
    MinimumAgeNotMetError,
    TermsAcceptanceRequiredError,
)
from app.candidates.schemas import ProfessionalRegistrationRequest
from app.candidates.services.register_professional import register_professional
from app.db.models import AppUser, Candidate
from app.db.models.enums import UserType
from app.identity.exceptions import (
    IdentityConflictError,
    IdentityProviderUnavailableError,
)
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration

TODAY = date(2026, 9, 13)
NOW = datetime(2026, 9, 13, 15, 30, tzinfo=UTC)


def registration_request(**overrides: object) -> ProfessionalRegistrationRequest:
    values: dict[str, object] = {
        "full_name": "Maria Souza",
        "cpf": "111.444.777-35",
        "birth_date": date(1970, 1, 1),
        "phone": "+55 51 99999-9999",
        "email": "Maria@example.com",
        "password": "LocalDemoOnly!2026",
        "terms_version_accepted": "v1",
        "city": "Porto Alegre",
        "state": "rs",
    }
    values.update(overrides)
    return ProfessionalRegistrationRequest.model_validate(values)


def test_registration_creates_linked_user_and_candidate(
    database_session: Session,
    identity_provider: FakeIdentityProvider,
) -> None:
    result = register_professional(
        registration_request(),
        session=database_session,
        identity_provider=identity_provider,
        today=TODAY,
        now=NOW,
    )

    user = database_session.get(AppUser, result.id)
    candidate = database_session.get(Candidate, result.id)

    assert user is not None
    assert candidate is not None
    assert user.email == "maria@example.com"
    assert user.identity_subject == identity_provider.subject
    assert user.user_type is UserType.CANDIDATE
    assert candidate.id == user.id
    assert candidate.cpf == "11144477735"
    assert candidate.age == 56
    assert candidate.state == "RS"
    assert candidate.terms_version_accepted == "v1"
    assert candidate.terms_accepted_at == NOW
    assert identity_provider.calls == ["register"]
    assert result.email_verification_required is True


def test_confirmed_identity_does_not_require_email_verification(
    database_session: Session,
    identity_provider: FakeIdentityProvider,
) -> None:
    identity_provider.confirmed = True

    result = register_professional(
        registration_request(),
        session=database_session,
        identity_provider=identity_provider,
        today=TODAY,
        now=NOW,
    )

    assert result.email_verification_required is False


def test_invalid_cpf_fails_before_provider_and_database(
    database_session: Session,
    identity_provider: FakeIdentityProvider,
) -> None:
    with pytest.raises(InvalidCpfError):
        register_professional(
            registration_request(cpf="111.111.111-11"),
            session=database_session,
            identity_provider=identity_provider,
            today=TODAY,
            now=NOW,
        )

    assert identity_provider.calls == []
    assert _user_count(database_session, email="maria@example.com") == 0


def test_professional_under_45_is_rejected_before_provider(
    database_session: Session,
    identity_provider: FakeIdentityProvider,
) -> None:
    with pytest.raises(MinimumAgeNotMetError):
        register_professional(
            registration_request(birth_date=date(1981, 9, 14)),
            session=database_session,
            identity_provider=identity_provider,
            today=TODAY,
            now=NOW,
        )

    assert identity_provider.calls == []
    assert _user_count(database_session, email="maria@example.com") == 0


def test_missing_terms_acceptance_is_rejected(
    database_session: Session,
    identity_provider: FakeIdentityProvider,
) -> None:
    with pytest.raises(TermsAcceptanceRequiredError):
        register_professional(
            registration_request(terms_version_accepted=None),
            session=database_session,
            identity_provider=identity_provider,
            today=TODAY,
            now=NOW,
        )

    assert identity_provider.calls == []
    assert _user_count(database_session, email="maria@example.com") == 0


def test_duplicate_cpf_is_a_conflict_without_second_provider_call(
    database_session: Session,
    identity_provider: FakeIdentityProvider,
) -> None:
    register_professional(
        registration_request(),
        session=database_session,
        identity_provider=identity_provider,
        today=TODAY,
        now=NOW,
    )

    with pytest.raises(CpfAlreadyRegisteredError):
        register_professional(
            registration_request(email="other@example.com"),
            session=database_session,
            identity_provider=identity_provider,
            today=TODAY,
            now=NOW,
        )

    assert identity_provider.calls == ["register"]
    assert _user_count(database_session, email="maria@example.com") == 1
    assert _user_count(database_session, email="other@example.com") == 0


def test_duplicate_email_is_a_conflict_without_second_provider_call(
    database_session: Session,
    identity_provider: FakeIdentityProvider,
) -> None:
    register_professional(
        registration_request(),
        session=database_session,
        identity_provider=identity_provider,
        today=TODAY,
        now=NOW,
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        register_professional(
            registration_request(cpf="222.555.888-46"),
            session=database_session,
            identity_provider=identity_provider,
            today=TODAY,
            now=NOW,
        )

    assert identity_provider.calls == ["register"]
    assert _user_count(database_session, email="maria@example.com") == 1


def test_provider_failure_rolls_back_local_records(
    database_session: Session,
    identity_provider: FakeIdentityProvider,
) -> None:
    identity_provider.error = IdentityProviderUnavailableError()

    with pytest.raises(IdentityProviderUnavailableError):
        register_professional(
            registration_request(),
            session=database_session,
            identity_provider=identity_provider,
            today=TODAY,
            now=NOW,
        )

    assert _user_count(database_session, email="maria@example.com") == 0
    assert _candidate_count(database_session, cpf="11144477735") == 0


def test_provider_identity_conflict_is_reported_on_email_and_rolls_back(
    database_session: Session,
    identity_provider: FakeIdentityProvider,
) -> None:
    identity_provider.error = IdentityConflictError()

    with pytest.raises(EmailAlreadyRegisteredError):
        register_professional(
            registration_request(),
            session=database_session,
            identity_provider=identity_provider,
            today=TODAY,
            now=NOW,
        )

    assert _user_count(database_session, email="maria@example.com") == 0


def test_database_failure_after_identity_creation_is_logged_and_recoverable(
    database_session: Session,
    identity_provider: FakeIdentityProvider,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with monkeypatch.context() as commit_failure:

        def fail_commit() -> None:
            raise IntegrityError("synthetic", None, Exception("synthetic"))

        commit_failure.setattr(database_session, "commit", fail_commit)
        with (
            caplog.at_level("WARNING", logger="app.identity"),
            pytest.raises(IntegrityError),
        ):
            register_professional(
                registration_request(),
                session=database_session,
                identity_provider=identity_provider,
                today=TODAY,
                now=NOW,
            )

    assert _user_count(database_session, email="maria@example.com") == 0
    assert _candidate_count(database_session, cpf="11144477735") == 0
    assert identity_provider.calls == ["register"]
    assert "identity_registration_incomplete" in caplog.text

    identity_provider.confirm_email(email="maria@example.com", code="123456")
    recovered = register_professional(
        registration_request(),
        session=database_session,
        identity_provider=identity_provider,
        today=TODAY,
        now=NOW,
    )

    assert recovered.email_verification_required is False
    assert _user_count(database_session, email="maria@example.com") == 1
    assert _candidate_count(database_session, cpf="11144477735") == 1
    assert identity_provider.calls == ["register", "confirm", "register"]


def test_lost_commit_acknowledgement_keeps_local_registration_and_logs_uncertainty(
    database_session: Session,
    identity_provider: FakeIdentityProvider,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    commit = database_session.commit

    def commit_then_lose_acknowledgement() -> None:
        commit()
        raise ConnectionError("synthetic lost acknowledgement")

    monkeypatch.setattr(database_session, "commit", commit_then_lose_acknowledgement)
    with (
        caplog.at_level("WARNING", logger="app.identity"),
        pytest.raises(ConnectionError),
    ):
        register_professional(
            registration_request(),
            session=database_session,
            identity_provider=identity_provider,
            today=TODAY,
            now=NOW,
        )

    assert _user_count(database_session, email="maria@example.com") == 1
    assert _candidate_count(database_session, cpf="11144477735") == 1
    assert identity_provider.calls == ["register"]
    assert "identity_registration_incomplete" in caplog.text


def _user_count(session: Session, *, email: str) -> int:
    statement = select(func.count()).select_from(AppUser).where(AppUser.email == email)
    return session.scalar(statement) or 0


def _candidate_count(session: Session, *, cpf: str) -> int:
    statement = select(func.count()).select_from(Candidate).where(Candidate.cpf == cpf)
    return session.scalar(statement) or 0
