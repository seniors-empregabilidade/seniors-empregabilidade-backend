from typing import Protocol

from app.companies.schemas.registry_record_response import RegistryRecordResponse


class CompanyRegistry(Protocol):
    def get_record(self, cnpj: str) -> RegistryRecordResponse: ...
