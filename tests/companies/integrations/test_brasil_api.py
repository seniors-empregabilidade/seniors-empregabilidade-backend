from collections.abc import Callable

import httpx2
import pytest

from app.companies.integrations.brasil_api import (
    BrasilAPIClient,
    RegistryProviderUnavailableError,
    RegistryRecordNotFoundError,
)


def client_for(handler: Callable[[httpx2.Request], httpx2.Response]) -> BrasilAPIClient:
    client = BrasilAPIClient(
        base_url="https://registry.example.invalid/api", timeout_seconds=1
    )
    client._client.close()
    client._client = httpx2.Client(
        base_url="https://registry.example.invalid/api",
        transport=httpx2.MockTransport(handler),
    )
    return client


def test_adapter_maps_only_owned_fields() -> None:
    def handler(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "cnpj": "11222333000181",
                "razao_social": "Synthetic SA",
                "nome_fantasia": "Synthetic",
                "cnae_fiscal": 6201501,
                "private": "must not escape",
            },
        )

    with client_for(handler) as client:
        result = client.get_record("11222333000181")
    assert result.model_dump() == {
        "cnpj": "11222333000181",
        "legal_name": "Synthetic SA",
        "trade_name": "Synthetic",
        "primary_cnae": "6201501",
    }


@pytest.mark.parametrize("status", [500, 201])
def test_adapter_translates_unexpected_status(status: int) -> None:
    with (
        client_for(lambda _: httpx2.Response(status)) as client,
        pytest.raises(RegistryProviderUnavailableError),
    ):
        client.get_record("11222333000181")


def test_adapter_translates_not_found() -> None:
    with (
        client_for(lambda _: httpx2.Response(404)) as client,
        pytest.raises(RegistryRecordNotFoundError),
    ):
        client.get_record("11222333000181")


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(200, content=b"not-json"),
        httpx2.Response(200, json={"cnpj": "11222333000181"}),
    ],
)
def test_adapter_rejects_invalid_payload(response: httpx2.Response) -> None:
    with (
        client_for(lambda _: response) as client,
        pytest.raises(RegistryProviderUnavailableError),
    ):
        client.get_record("11222333000181")


def test_adapter_does_not_retry_connection_failure() -> None:
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        raise httpx2.ConnectError("unavailable", request=request)

    with client_for(handler) as client, pytest.raises(RegistryProviderUnavailableError):
        client.get_record("11222333000181")
    assert calls == 1


def test_adapter_translates_timeout_without_retry() -> None:
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        raise httpx2.ReadTimeout("timed out", request=request)

    with client_for(handler) as client, pytest.raises(RegistryProviderUnavailableError):
        client.get_record("11222333000181")
    assert calls == 1


def test_adapter_rejects_a_record_for_another_cnpj() -> None:
    response = httpx2.Response(
        200,
        json={
            "cnpj": "11444777000161",
            "razao_social": "Wrong Company SA",
            "nome_fantasia": None,
            "cnae_fiscal": 6201501,
        },
    )
    with (
        client_for(lambda _: response) as client,
        pytest.raises(RegistryProviderUnavailableError),
    ):
        client.get_record("11222333000181")


@pytest.mark.parametrize(
    "changes",
    [
        {"razao_social": "x" * 201},
        {"razao_social": "  "},
        {"cnae_fiscal": ""},
        {"cnae_fiscal": "text"},
        {"cnae_fiscal": -1},
        {"cnae_fiscal": True},
        {"cnae_fiscal": None},
        {"cnae_fiscal": 0},
        {"cnae_fiscal": "12345678"},
        {"nome_fantasia": "x" * 201},
    ],
)
def test_provider_values_are_validated_before_persistence(
    changes: dict[str, object],
) -> None:
    payload = {
        "cnpj": "11222333000181",
        "razao_social": "Synthetic Company",
        "cnae_fiscal": 6201501,
    }
    payload.update(changes)
    with (
        client_for(lambda _: httpx2.Response(200, json=payload)) as client,
        pytest.raises(RegistryProviderUnavailableError),
    ):
        client.get_record("11222333000181")
