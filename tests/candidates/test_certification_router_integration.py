import os
from collections.abc import Iterator
from datetime import date
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from app.candidates.domain.certificate_document import MAX_DOCUMENT_BYTES
from app.db.models.app_user import AppUser
from app.db.models.attached_certificate import AttachedCertificate
from app.db.models.candidate import Candidate
from app.db.models.certification import Certification
from app.db.models.enums import UserType
from app.db.models.resume import Resume
from app.db.session import get_session_factory
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from app.storage.dependencies import get_document_storage
from tests.identity.fakes import FakeIdentityProvider
from tests.storage.fakes import FakeDocumentStorage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

PATH = "/api/v1/professionals/me/certifications"
EMAIL_DOMAIN = "certification-router.example.invalid"
PDF = b"%PDF-1.7\nsynthetic"
PNG = b"\x89PNG\r\n\x1a\nsynthetic"
VALID_BODY = {
    "name": "Gestão de Projetos",
    "issuer": "Instituto Sintético",
    "issued_date": "2020-03-01",
    "expiration_date": "2025-03-01",
}


class RoleIdentityProvider(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token not in {"owner", "other", "admin", "company"}:
            raise InvalidAccessTokenError
        return f"certification-{token}"


def auth(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {role}"}


@pytest.fixture
def storage(application: FastAPI) -> FakeDocumentStorage:
    fake = FakeDocumentStorage()
    application.dependency_overrides[get_identity_provider] = RoleIdentityProvider
    application.dependency_overrides[get_document_storage] = lambda: fake
    return fake


@pytest.fixture
def users() -> Iterator[dict[str, UUID]]:
    ids: dict[str, UUID] = {}
    with get_session_factory().begin() as session:
        for role, user_type in [
            ("owner", UserType.CANDIDATE),
            ("other", UserType.CANDIDATE),
            ("admin", UserType.ADMINISTRATOR),
            ("company", UserType.COMPANY),
        ]:
            user = AppUser(
                email=f"{role}@{EMAIL_DOMAIN}",
                identity_subject=f"certification-{role}",
                user_type=user_type,
            )
            session.add(user)
            session.flush()
            if user_type == UserType.CANDIDATE:
                session.add(
                    Candidate(
                        id=user.id,
                        full_name="Pessoa Sintética",
                        cpf=f"{uuid4().int % 10**11:011d}",
                        birth_date=date(1970, 1, 1),
                        phone="51999990000",
                    )
                )
            ids[role] = user.id
    yield ids
    with get_session_factory().begin() as session:
        session.execute(delete(AppUser).where(AppUser.id.in_(ids.values())))


def add_certification(user_id: UUID, *, with_document: bool = False) -> UUID:
    with get_session_factory().begin() as session:
        resume = session.scalar(select(Resume).where(Resume.candidate_id == user_id))
        if resume is None:
            resume = Resume(candidate_id=user_id)
            session.add(resume)
            session.flush()
        certification = Certification(resume_id=resume.id, name="Excel Avançado")
        session.add(certification)
        session.flush()
        if with_document:
            session.add(
                AttachedCertificate(
                    certification_id=certification.id,
                    object_key=f"certifications/{certification.id}/existing",
                    filename="antigo.pdf",
                    content_type="application/pdf",
                    size_bytes=10,
                )
            )
        return certification.id


def stored(certification_id: UUID) -> Certification | None:
    with get_session_factory()() as session:
        return session.get(Certification, certification_id)


def stored_document(certification_id: UUID) -> AttachedCertificate | None:
    with get_session_factory()() as session:
        return session.scalar(
            select(AttachedCertificate).where(
                AttachedCertificate.certification_id == certification_id
            )
        )


def upload(
    client: TestClient,
    certification_id: UUID,
    content: bytes = PDF,
    filename: str = "certificado.pdf",
    role: str = "owner",
) -> httpx2.Response:
    return client.put(
        f"{PATH}/{certification_id}/document",
        files={"file": (filename, content, "application/octet-stream")},
        headers=auth(role),
    )


def test_create_is_persisted_without_document(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    response = client.post(PATH, json=VALID_BODY, headers=auth("owner"))

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["document"] is None
    certification = stored(UUID(response.json()["id"]))
    assert certification is not None
    assert certification.issuer == "Instituto Sintético"


def test_only_name_is_required(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    response = client.post(PATH, json={"name": "  NR-10  "}, headers=auth("owner"))

    assert response.status_code == 201
    assert response.json()["name"] == "NR-10"
    assert response.json()["issued_date"] is None


def test_expiration_before_issue_is_rejected(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    response = client.post(
        PATH,
        json={**VALID_BODY, "expiration_date": "2019-01-01"},
        headers=auth("owner"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_certification_period"
    assert "expiration_date" in response.json()["errors"]


def test_update_changes_only_sent_fields(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"], with_document=True)

    response = client.patch(
        f"{PATH}/{certification_id}", json={"issuer": "SENAI"}, headers=auth("owner")
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Excel Avançado"
    assert response.json()["document"]["filename"] == "antigo.pdf"
    certification = stored(certification_id)
    assert certification is not None
    assert certification.issuer == "SENAI"


def test_name_cannot_be_cleared(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"])

    response = client.patch(
        f"{PATH}/{certification_id}", json={"name": None}, headers=auth("owner")
    )

    assert response.status_code == 422
    assert "body.name" in response.json()["errors"]


def test_delete_removes_certification_and_its_file(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"], with_document=True)
    key = f"certifications/{certification_id}/existing"
    storage.objects[key] = (PDF, "application/pdf")

    response = client.delete(f"{PATH}/{certification_id}", headers=auth("owner"))

    assert response.status_code == 204
    assert stored(certification_id) is None
    assert stored_document(certification_id) is None
    assert key not in storage.objects


def test_delete_survives_storage_failure(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"], with_document=True)
    storage.unavailable = True

    response = client.delete(f"{PATH}/{certification_id}", headers=auth("owner"))

    assert response.status_code == 204
    assert stored(certification_id) is None


def test_upload_stores_file_and_metadata(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"])

    response = upload(client, certification_id, PNG, "C:\\fotos\\certificado.png")

    assert response.status_code == 200
    document = response.json()["document"]
    assert document["filename"] == "certificado.png"
    assert document["content_type"] == "image/png"
    assert document["size_bytes"] == len(PNG)
    attached = stored_document(certification_id)
    assert attached is not None
    assert attached.object_key.startswith(f"certifications/{certification_id}/")
    assert storage.objects[attached.object_key] == (PNG, "image/png")


def test_upload_replaces_the_previous_file(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"], with_document=True)
    old_key = f"certifications/{certification_id}/existing"
    storage.objects[old_key] = (PDF, "application/pdf")

    response = upload(client, certification_id, PNG, "novo.png")

    assert response.status_code == 200
    attached = stored_document(certification_id)
    assert attached is not None
    assert attached.filename == "novo.png"
    assert list(storage.objects) == [attached.object_key]


def test_unsupported_file_is_rejected_before_storage(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"])

    response = upload(client, certification_id, b"<html>", "certificado.pdf")

    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_document_type"
    assert "file" in response.json()["errors"]
    assert storage.calls == []
    assert stored_document(certification_id) is None


def test_oversized_file_is_rejected_before_storage(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"])

    response = upload(client, certification_id, PDF + b"\x00" * MAX_DOCUMENT_BYTES)

    assert response.status_code == 422
    assert response.json()["code"] == "document_too_large"
    assert storage.calls == []


def test_missing_file_is_a_validation_error(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"])

    response = client.put(f"{PATH}/{certification_id}/document", headers=auth("owner"))

    assert response.status_code == 422
    assert storage.calls == []


def test_unavailable_storage_keeps_no_row(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"])
    storage.unavailable = True

    response = upload(client, certification_id)

    assert response.status_code == 503
    assert response.json()["code"] == "document_storage_unavailable"
    assert stored_document(certification_id) is None


def test_database_failure_removes_the_uploaded_file(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"])

    def reject_attachment_flush(session: Session, *_: object) -> None:
        if any(isinstance(row, AttachedCertificate) for row in session.new):
            raise RuntimeError("Synthetic attachment persistence failure")

    event.listen(Session, "before_flush", reject_attachment_flush)
    try:
        response = upload(client, certification_id)
    finally:
        event.remove(Session, "before_flush", reject_attachment_flush)

    assert response.status_code == 500
    assert storage.calls == ["put", "delete"]
    assert storage.objects == {}
    assert stored_document(certification_id) is None


def test_remove_document_keeps_the_certification(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"], with_document=True)
    key = f"certifications/{certification_id}/existing"
    storage.objects[key] = (PDF, "application/pdf")

    response = client.delete(
        f"{PATH}/{certification_id}/document", headers=auth("owner")
    )

    assert response.status_code == 204
    assert stored(certification_id) is not None
    assert stored_document(certification_id) is None
    assert storage.objects == {}


def test_remove_missing_document_is_not_found(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"])

    response = client.delete(
        f"{PATH}/{certification_id}/document", headers=auth("owner")
    )

    assert response.status_code == 404
    assert response.json()["code"] == "certification_document_not_found"


def test_owner_gets_a_short_lived_link(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"], with_document=True)

    response = client.get(f"{PATH}/{certification_id}/document", headers=auth("owner"))

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["url"] == (
        "https://storage.example.invalid/"
        f"certifications/{certification_id}/existing?expires_in=300"
    )
    assert response.json()["expires_at"]


def test_link_without_document_is_not_found(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"])

    response = client.get(f"{PATH}/{certification_id}/document", headers=auth("owner"))

    assert response.status_code == 404
    assert response.json()["code"] == "certification_document_not_found"


def test_administrator_gets_a_professionals_link(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"], with_document=True)

    response = client.get(
        f"/api/v1/professionals/{users['owner']}/certifications/"
        f"{certification_id}/document",
        headers=auth("admin"),
    )

    assert response.status_code == 200
    assert response.json()["url"].startswith("https://storage.example.invalid/")


@pytest.mark.parametrize("role", ["company", "owner", "other"])
def test_only_administrators_use_the_professional_route(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID], role: str
) -> None:
    certification_id = add_certification(users["owner"], with_document=True)

    response = client.get(
        f"/api/v1/professionals/{users['owner']}/certifications/"
        f"{certification_id}/document",
        headers=auth(role),
    )

    assert response.status_code == 403
    assert storage.calls == []


def test_administrator_route_checks_the_owner(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"], with_document=True)

    response = client.get(
        f"/api/v1/professionals/{users['other']}/certifications/"
        f"{certification_id}/document",
        headers=auth("admin"),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "certification_not_found"


def test_other_candidates_certification_is_not_found(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    certification_id = add_certification(users["owner"], with_document=True)
    path = f"{PATH}/{certification_id}"

    responses = [
        client.patch(path, json={"name": "Invasor"}, headers=auth("other")),
        client.delete(path, headers=auth("other")),
        upload(client, certification_id, role="other"),
        client.get(f"{path}/document", headers=auth("other")),
        client.delete(f"{path}/document", headers=auth("other")),
    ]

    assert [response.status_code for response in responses] == [404] * 5
    assert {response.json()["code"] for response in responses} == {
        "certification_not_found"
    }
    assert storage.calls == []
    certification = stored(certification_id)
    assert certification is not None
    assert certification.name == "Excel Avançado"


def test_company_cannot_manage_certifications(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    response = client.post(PATH, json=VALID_BODY, headers=auth("company"))

    assert response.status_code == 403


def test_certifications_require_a_token(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    assert client.post(PATH, json=VALID_BODY).status_code == 401


def test_profile_lists_certifications_with_document_metadata(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    with_document = add_certification(users["owner"], with_document=True)
    without_document = add_certification(users["owner"])

    response = client.get("/api/v1/professionals/me", headers=auth("owner"))

    assert response.status_code == 200
    certifications = {item["id"]: item for item in response.json()["certifications"]}
    assert certifications[str(with_document)]["document"]["filename"] == "antigo.pdf"
    assert certifications[str(without_document)]["document"] is None
    assert "object_key" not in str(response.json())


def test_unconfigured_storage_is_unavailable(
    application: FastAPI, client: TestClient, users: dict[str, UUID]
) -> None:
    application.dependency_overrides[get_identity_provider] = RoleIdentityProvider
    certification_id = add_certification(users["owner"])

    response = upload(client, certification_id)

    assert response.status_code == 503
    assert response.json()["code"] == "document_storage_unavailable"


def test_certifications_work_without_configured_storage(
    application: FastAPI, client: TestClient, users: dict[str, UUID]
) -> None:
    application.dependency_overrides[get_identity_provider] = RoleIdentityProvider
    certification_id = add_certification(users["owner"])

    response = client.delete(f"{PATH}/{certification_id}", headers=auth("owner"))

    assert response.status_code == 204
    assert stored(certification_id) is None
