import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.companies.integrations.brasil_api import CompanyRegistry
from app.companies.router import get_company_registry
from app.companies.schemas.registry_record_response import RegistryRecordResponse
from app.core.passwords import verify_password
from app.db.models import Address, AppUser, Company
from app.db.models.enums import CompanyStatus, UserType
from app.db.session import get_session_factory

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

TEST_EMAIL = "registration-test@company.example.invalid"
TEST_CNPJ = "11222333000181"
SECOND_EMAIL = "second@company.example.invalid"


class FakeRegistry:
    def get_record(self, cnpj: str) -> RegistryRecordResponse:
        return RegistryRecordResponse(
            cnpj=cnpj,
            legal_name="Synthetic Registry Company SA",
            trade_name="Provider name ignored",
            primary_cnae="6201501",
        )


@pytest.fixture(autouse=True)
def clean_registration_rows() -> Iterator[None]:
    factory = get_session_factory()
    with factory.begin() as session:
        company = session.scalar(select(Company).where(Company.cnpj == TEST_CNPJ))
        if company:
            address_id = company.address_id
            session.execute(delete(AppUser).where(AppUser.id == company.id))
            if address_id:
                session.execute(delete(Address).where(Address.id == address_id))
        session.execute(delete(AppUser).where(AppUser.email == TEST_EMAIL))
        session.execute(delete(AppUser).where(AppUser.email == SECOND_EMAIL))
    yield
    with factory.begin() as session:
        company = session.scalar(select(Company).where(Company.cnpj == TEST_CNPJ))
        if company:
            address_id = company.address_id
            session.execute(delete(AppUser).where(AppUser.id == company.id))
            if address_id:
                session.execute(delete(Address).where(Address.id == address_id))
        session.execute(delete(AppUser).where(AppUser.email == TEST_EMAIL))
        session.execute(delete(AppUser).where(AppUser.email == SECOND_EMAIL))


def test_post_persists_complete_company_atomically(
    application: FastAPI, client: TestClient
) -> None:
    def registry_dependency() -> Iterator[CompanyRegistry]:
        yield FakeRegistry()

    application.dependency_overrides[get_company_registry] = registry_dependency

    response = client.post(
        "/api/v1/companies",
        json={
            "cnpj": "11.222.333/0001-81",
            "display_name": "Chosen Display Name",
            "address": {
                "street": "Synthetic Street",
                "number": "42",
                "complement": None,
                "neighborhood": "Test District",
                "city": "Test City",
                "state": "sp",
                "zip_code": "12345-678",
            },
            "corporate_email": "registration-test@Company.Example.Invalid",
            "password": "SyntheticPass!2026",
            "terms_accepted": True,
            "terms_version": "2026-08",
        },
    )

    assert response.status_code == 201
    assert set(response.json()) == {"id", "email", "status"}
    factory = get_session_factory()
    with factory() as session:
        company = session.scalar(select(Company).where(Company.cnpj == TEST_CNPJ))
        assert company is not None
        user = session.get(AppUser, company.id)
        address = session.get(Address, company.address_id)
        assert user is not None and address is not None
        assert user.user_type == UserType.COMPANY
        assert verify_password(user.password_hash, "SyntheticPass!2026")
        assert company.status == CompanyStatus.PENDING
        assert company.legal_name == "Synthetic Registry Company SA"
        assert company.trade_name == "Chosen Display Name"
        assert company.terms_version_accepted == "2026-08"
        assert company.terms_accepted_at is not None
        assert address.neighborhood == "Test District"
        assert address.state == "SP" and address.zip_code == "12345678"


def test_duplicate_cnpj_rolls_back_new_user_and_address(
    application: FastAPI, client: TestClient
) -> None:
    test_post_persists_complete_company_atomically(application, client)
    response = client.post(
        "/api/v1/companies",
        json={
            "cnpj": TEST_CNPJ,
            "display_name": "Duplicate",
            "address": {
                "street": "Other",
                "number": "1",
                "neighborhood": "Other",
                "city": "Other",
                "state": "RS",
                "zip_code": "90000000",
            },
            "corporate_email": SECOND_EMAIL,
            "password": "SyntheticPass!2026",
            "terms_accepted": True,
            "terms_version": "2026-08",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "company_cnpj_conflict"
    factory = get_session_factory()
    with factory() as session:
        assert (
            session.scalar(select(AppUser).where(AppUser.email == SECOND_EMAIL)) is None
        )


def test_database_uniqueness_handles_concurrent_cnpj_registration(
    application: FastAPI, client: TestClient
) -> None:
    barrier = Barrier(2)

    class ConcurrentRegistry(FakeRegistry):
        def get_record(self, cnpj: str) -> RegistryRecordResponse:
            barrier.wait(timeout=5)
            return super().get_record(cnpj)

    def registry_dependency() -> Iterator[CompanyRegistry]:
        yield ConcurrentRegistry()

    application.dependency_overrides[get_company_registry] = registry_dependency

    def submit(email: str) -> int:
        response = client.post(
            "/api/v1/companies",
            json={
                "cnpj": TEST_CNPJ,
                "display_name": "Concurrent",
                "address": {
                    "street": "Concurrent Street",
                    "number": "1",
                    "neighborhood": "Concurrent District",
                    "city": "Concurrent City",
                    "state": "SP",
                    "zip_code": "12345678",
                },
                "corporate_email": email,
                "password": "SyntheticPass!2026",
                "terms_accepted": True,
                "terms_version": "2026-08",
            },
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(submit, (TEST_EMAIL, SECOND_EMAIL)))

    assert statuses == [201, 409]
    factory = get_session_factory()
    with factory() as session:
        companies = session.scalars(
            select(Company).where(Company.cnpj == TEST_CNPJ)
        ).all()
        assert len(companies) == 1
