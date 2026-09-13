import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from threading import Barrier, Lock

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.candidates.schemas import ProfessionalRegistrationRequest
from app.candidates.services import register_professional
from app.core.errors import ProblemException
from app.db.models import AppUser
from app.db.session import get_engine
from app.identity.registered_identity import RegisteredIdentity
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration

TODAY = date(2026, 9, 13)
NOW = datetime(2026, 9, 13, 15, 30, tzinfo=UTC)


class CountingIdentityProvider(FakeIdentityProvider):
    def __init__(self) -> None:
        super().__init__()
        self._lock = Lock()
        self.registration_count = 0

    def register(self, *, email: str, password: str) -> RegisteredIdentity:
        with self._lock:
            self.registration_count += 1
            count = self.registration_count
        return RegisteredIdentity(f"concurrent-subject-{count}", False)


def registration_request(**overrides: object) -> ProfessionalRegistrationRequest:
    values: dict[str, object] = {
        "full_name": "Concurrent Candidate",
        "cpf": "111.444.777-35",
        "birth_date": date(1970, 1, 1),
        "phone": "+55 51 99999-9999",
        "email": "concurrent@example.com",
        "password": "LocalDemoOnly!2026",
        "terms_version_accepted": "v1",
    }
    values.update(overrides)
    return ProfessionalRegistrationRequest.model_validate(values)


@pytest.fixture(autouse=True)
def clean_concurrent_registrations() -> Iterator[None]:
    if os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1":
        pytest.skip("requires RUN_DATABASE_INTEGRATION_TESTS=1 and PostgreSQL")

    emails = {
        "concurrent@example.com",
        "cpf-first@example.com",
        "cpf-second@example.com",
    }
    _delete_users(emails)
    yield
    _delete_users(emails)


def _delete_users(emails: set[str]) -> None:
    with get_engine().begin() as connection:
        connection.execute(delete(AppUser).where(AppUser.email.in_(emails)))


def test_concurrent_duplicate_email_creates_only_one_identity() -> None:
    provider = CountingIdentityProvider()
    barrier = Barrier(2)
    requests = (
        registration_request(),
        registration_request(cpf="222.555.888-46"),
    )

    outcomes = _run_concurrently(requests, barrier, provider)

    assert sorted(outcomes) == ["created", "email_already_registered"]
    assert provider.registration_count == 1


def test_concurrent_duplicate_cpf_creates_only_one_identity() -> None:
    provider = CountingIdentityProvider()
    barrier = Barrier(2)
    requests = (
        registration_request(email="cpf-first@example.com"),
        registration_request(email="cpf-second@example.com"),
    )

    outcomes = _run_concurrently(requests, barrier, provider)

    assert sorted(outcomes) == ["cpf_already_registered", "created"]
    assert provider.registration_count == 1


def _run_concurrently(
    requests: tuple[ProfessionalRegistrationRequest, ProfessionalRegistrationRequest],
    barrier: Barrier,
    provider: CountingIdentityProvider,
) -> list[str]:
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_attempt_registration, request, barrier, provider)
            for request in requests
        ]
        return [future.result(timeout=10) for future in futures]


def _attempt_registration(
    request: ProfessionalRegistrationRequest,
    barrier: Barrier,
    provider: CountingIdentityProvider,
) -> str:
    with Session(bind=get_engine(), expire_on_commit=False, autoflush=False) as session:
        barrier.wait(timeout=5)
        try:
            register_professional(
                request,
                session=session,
                identity_provider=provider,
                today=TODAY,
                now=NOW,
            )
        except ProblemException as exc:
            return exc.code
    return "created"
