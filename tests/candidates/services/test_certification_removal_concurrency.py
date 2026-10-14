import os
import time
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, text

from app.candidates.services.certification_documents import remove_document
from app.candidates.services.certifications import (
    attached_document,
    get_own_certification,
    remove_certification,
)
from app.db.models.app_user import AppUser
from app.db.models.attached_certificate import AttachedCertificate
from app.db.models.candidate import Candidate
from app.db.models.certification import Certification
from app.db.models.enums import UserType
from app.db.models.resume import Resume
from app.db.session import get_engine, get_session_factory
from app.storage.document_storage import DocumentStorage
from tests.storage.fakes import FakeDocumentStorage

pytestmark = pytest.mark.integration

Removal = Callable[..., None]


@pytest.fixture
def certification() -> Iterator[tuple[UUID, UUID]]:
    if os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1":
        pytest.skip("requires RUN_DATABASE_INTEGRATION_TESTS=1 and PostgreSQL")

    with get_session_factory().begin() as session:
        user = AppUser(
            email=f"{uuid4()}@certification-concurrency.example.invalid",
            identity_subject=f"certification-concurrency-{uuid4()}",
            user_type=UserType.CANDIDATE,
        )
        session.add(user)
        session.flush()
        session.add(
            Candidate(
                id=user.id,
                full_name="Pessoa Sintética",
                cpf=f"{uuid4().int % 10**11:011d}",
                birth_date=date(1970, 1, 1),
                phone="51999990000",
            )
        )
        resume = Resume(candidate_id=user.id)
        session.add(resume)
        session.flush()
        record = Certification(resume_id=resume.id, name="Excel Avançado")
        session.add(record)
        session.flush()
        session.add(
            AttachedCertificate(
                certification_id=record.id,
                object_key=f"certifications/{record.id}/old",
                filename="antigo.pdf",
                content_type="application/pdf",
                size_bytes=10,
            )
        )
        ids = (user.id, record.id)
    yield ids
    with get_session_factory().begin() as session:
        session.execute(delete(AppUser).where(AppUser.id == ids[0]))


@pytest.mark.parametrize("remove", [remove_document, remove_certification])
def test_removal_deletes_the_file_of_a_concurrent_replacement(
    remove: Removal, certification: tuple[UUID, UUID]
) -> None:
    user_id, certification_id = certification
    new_key = f"certifications/{certification_id}/new"
    storage = FakeDocumentStorage()
    storage.objects[new_key] = (b"%PDF-", "application/pdf")

    with get_session_factory()() as replacing, ThreadPoolExecutor(1) as pool:
        # Holds the row lock the upload takes while it swaps the stored file.
        get_own_certification(user_id, certification_id, replacing, lock=True)
        attached = attached_document(certification_id, replacing)
        assert attached is not None
        attached.object_key = new_key
        replacing.flush()

        removal = pool.submit(_remove, remove, user_id, certification_id, storage)
        _wait_until_blocked(removal)
        replacing.commit()
        removal.result(timeout=10)

    assert new_key not in storage.objects
    with get_session_factory()() as session:
        assert attached_document(certification_id, session) is None


def _remove(
    remove: Removal, user_id: UUID, certification_id: UUID, storage: DocumentStorage
) -> None:
    with get_session_factory()() as session:
        remove(user_id, certification_id, session=session, storage=storage)


def _wait_until_blocked(removal: Future[None]) -> None:
    deadline = time.monotonic() + 10
    query = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() AND wait_event_type = 'Lock'"
    )
    while time.monotonic() < deadline and not removal.done():
        with get_engine().connect() as connection:
            if connection.scalar(query):
                return
        time.sleep(0.02)
    pytest.fail("the removal never waited for the replacement's lock")
