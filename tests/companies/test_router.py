from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.companies.integrations.brasil_api import (
    CompanyRegistry,
    RegistryProviderUnavailableError,
    RegistryRecordNotFoundError,
)
from app.companies.router import get_company_registry
from app.companies.schemas.registry_record_response import RegistryRecordResponse


class FakeRegistry:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    def get_record(self, cnpj: str) -> RegistryRecordResponse:
        self.calls.append(cnpj)
        if self.error:
            raise self.error
        return RegistryRecordResponse(
            cnpj=cnpj,
            legal_name="Synthetic Company SA",
            trade_name=None,
            primary_cnae="6201501",
        )


def override_registry(app: FastAPI, fake: FakeRegistry) -> None:
    def dependency() -> Iterator[CompanyRegistry]:
        yield fake

    app.dependency_overrides[get_company_registry] = dependency


def test_get_registry_record_returns_owned_dto(
    application: FastAPI, client: TestClient
) -> None:
    fake = FakeRegistry()
    override_registry(application, fake)

    response = client.get("/api/v1/company-registry-records/11.222.333%2F0001-81")

    assert response.status_code == 200
    assert response.json() == {
        "cnpj": "11222333000181",
        "legal_name": "Synthetic Company SA",
        "trade_name": None,
        "primary_cnae": "6201501",
    }
    assert fake.calls == ["11222333000181"]


def test_invalid_cnpj_does_not_call_registry(
    application: FastAPI, client: TestClient
) -> None:
    fake = FakeRegistry()
    override_registry(application, fake)

    response = client.get("/api/v1/company-registry-records/00000000000000")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "invalid_cnpj"
    assert fake.calls == []


def test_registry_failures_have_stable_problem_codes(
    application: FastAPI, client: TestClient
) -> None:
    for error, expected_status, expected_code in (
        (RegistryRecordNotFoundError(), 404, "cnpj_not_found"),
        (RegistryProviderUnavailableError(), 503, "cnpj_provider_unavailable"),
    ):
        override_registry(application, FakeRegistry(error))
        response = client.get("/api/v1/company-registry-records/11222333000181")
        assert response.status_code == expected_status
        assert response.json()["code"] == expected_code
