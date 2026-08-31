from typing import Protocol

import httpx2
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.companies.schemas.registry_record_response import RegistryRecordResponse


class RegistryRecordNotFoundError(Exception):
    pass


class RegistryProviderUnavailableError(Exception):
    pass


class CompanyRegistry(Protocol):
    def get_record(self, cnpj: str) -> RegistryRecordResponse: ...


class _RegistryPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cnpj: str = Field(pattern=r"^[0-9]{14}$")
    razao_social: str = Field(min_length=1)
    nome_fantasia: str | None = None
    cnae_fiscal: str | int


class BrasilAPIClient:
    def __init__(self, *, base_url: str, timeout_seconds: float) -> None:
        self._client = httpx2.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds
        )

    def get_record(self, cnpj: str) -> RegistryRecordResponse:
        try:
            response = self._client.get(f"/cnpj/v1/{cnpj}")
        except (httpx2.TimeoutException, httpx2.RequestError) as exc:
            raise RegistryProviderUnavailableError from exc
        if response.status_code == 404:
            raise RegistryRecordNotFoundError
        if response.status_code != 200:
            raise RegistryProviderUnavailableError
        try:
            payload = _RegistryPayload.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise RegistryProviderUnavailableError from exc
        if payload.cnpj != cnpj:
            raise RegistryProviderUnavailableError
        return RegistryRecordResponse(
            cnpj=payload.cnpj,
            legal_name=payload.razao_social,
            trade_name=payload.nome_fantasia or None,
            primary_cnae=str(payload.cnae_fiscal),
        )

    def __enter__(self) -> BrasilAPIClient:
        return self

    def __exit__(self, *_: object) -> None:
        self._client.close()
