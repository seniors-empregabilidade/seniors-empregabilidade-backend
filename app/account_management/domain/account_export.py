"""Columns of the account CSV export, in the administrator's language.

The labels repeat the ones the administrator sees on the "Cadastros" screen,
so the spreadsheet reads the same as the list it was exported from. Only
fields the list already shows are exported: no CPF, phone, birth date,
address, résumé content, documents or block justification.
"""

from collections.abc import Sequence
from datetime import datetime

from app.core.csv_document import local_day
from app.db.models.enums import AccountStatus, CompanyStatus, UserType

ACCOUNT_EXPORT_HEADER = (
    "Nome",
    "Tipo",
    "E-mail",
    "Status da conta",
    "Situação da empresa",
    "Currículo",
    "Campos faltantes",
    "Data de cadastro",
)

_USER_TYPES = {UserType.CANDIDATE: "Profissional", UserType.COMPANY: "Empresa"}
_ACCOUNT_STATUSES = {
    AccountStatus.ACTIVE: "Ativa",
    AccountStatus.SUSPENDED: "Suspensa",
    AccountStatus.BLOCKED: "Bloqueada",
}
_COMPANY_STATUSES = {
    CompanyStatus.PENDING: "Pendente",
    CompanyStatus.APPROVED: "Aprovada",
    CompanyStatus.REJECTED: "Recusada",
    CompanyStatus.BLOCKED: "Bloqueada",
}
# The US-08 field keys from `missing_resume_fields`, as the résumé screens name them.
_MISSING_FIELDS = {
    "city": "Cidade",
    "state": "Estado",
    "summary": "Resumo profissional",
    "experiences": "Experiência profissional",
    "education": "Formação",
    "skills": "Habilidades",
}


def account_export_row(
    *,
    display_name: str | None,
    user_type: UserType,
    email: str,
    account_status: AccountStatus,
    company_status: CompanyStatus | None,
    missing_fields: Sequence[str] | None,
    created_at: datetime,
) -> tuple[str, ...]:
    """One CSV row; company columns are blank for a candidate and vice versa."""
    is_candidate = user_type == UserType.CANDIDATE
    return (
        display_name or "",
        _USER_TYPES[user_type],
        email,
        _ACCOUNT_STATUSES[account_status],
        _COMPANY_STATUSES[company_status] if company_status else "",
        _resume_situation(missing_fields) if is_candidate else "",
        ", ".join(_MISSING_FIELDS[field] for field in missing_fields or ()),
        local_day(created_at),
    )


def _resume_situation(missing_fields: Sequence[str] | None) -> str:
    return "Incompleto" if missing_fields else "Completo"
