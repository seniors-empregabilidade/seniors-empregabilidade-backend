from pydantic import BaseModel


class RegistryRecordResponse(BaseModel):
    cnpj: str
    legal_name: str
    trade_name: str | None
    primary_cnae: str
