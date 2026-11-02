"""Rows of the dashboard CSV export, in the administrator's language.

The file is a two-column "Item;Valor" sheet: when it was generated, every
filter as the dashboard shows it, then each indicator. Keeping the filters in
the file lets a spreadsheet opened weeks later say which numbers it holds.
"""

from collections.abc import Mapping
from datetime import date, datetime
from enum import StrEnum

from app.core.csv_document import brazilian_date, local_minute
from app.db.models.enums import (
    AccountStatus,
    ApplicationStatus,
    AvailabilityStatus,
    CompanyStatus,
    JobStatus,
)
from app.indicators.schemas.indicator_filters import IndicatorFilters

INDICATOR_EXPORT_HEADER = ("Item", "Valor")

_NO_DATE_LIMIT = "Sem limite"
_ACCOUNT_STATUSES = {
    AccountStatus.ACTIVE: "Ativas",
    AccountStatus.BLOCKED: "Bloqueadas",
    AccountStatus.SUSPENDED: "Suspensas",
}
_AVAILABILITIES = {
    AvailabilityStatus.AVAILABLE: "Disponível",
    AvailabilityStatus.UNAVAILABLE: "Indisponível",
}
_COMPANY_STATUSES = {
    CompanyStatus.PENDING: "Pendente",
    CompanyStatus.APPROVED: "Aprovada",
    CompanyStatus.REJECTED: "Recusada",
    CompanyStatus.BLOCKED: "Bloqueada",
}
_JOB_STATUSES = {
    JobStatus.DRAFT: "Rascunho",
    JobStatus.UNDER_REVIEW: "Em revisão",
    JobStatus.PUBLISHED: "Publicada",
    JobStatus.PAUSED: "Pausada",
    JobStatus.EXPIRED: "Expirada",
    JobStatus.CLOSED: "Encerrada",
}
_APPLICATION_STATUSES = {
    ApplicationStatus.APPLIED: "Enviada",
    ApplicationStatus.UNDER_REVIEW: "Em análise",
    ApplicationStatus.IN_SELECTION_PROCESS: "Em seleção",
    ApplicationStatus.HIRED: "Contratado",
    ApplicationStatus.NOT_SELECTED: "Não selecionado",
    ApplicationStatus.WITHDRAWN: "Desistência",
    ApplicationStatus.EXPIRED: "Expirada",
}
# Indicator keys from `IndicatorTotals` and `IndicatorSegments`, in dashboard order.
_INDICATORS = (
    ("candidates", "Profissionais"),
    ("companies", "Empresas"),
    ("jobs", "Vagas"),
    ("applications", "Candidaturas"),
    ("matches", "Matches"),
    ("candidates_without_placement", "Profissionais sem colocação"),
    ("candidates_with_unknown_employment", "Situação profissional não informada"),
    ("incomplete_resumes", "Currículos incompletos"),
)


def indicator_export_rows(
    *,
    generated_at: datetime,
    filters: IndicatorFilters,
    counts: Mapping[str, int],
) -> list[tuple[str, str]]:
    return [
        ("Gerado em", local_minute(generated_at)),
        ("Data inicial", _day(filters.start_date)),
        ("Data final", _day(filters.end_date)),
        (
            "Status das contas",
            _label(_ACCOUNT_STATUSES, filters.account_status, "Todos"),
        ),
        (
            "Disponibilidade do profissional",
            _label(_AVAILABILITIES, filters.candidate_availability, "Todas"),
        ),
        (
            "Situação da empresa",
            _label(_COMPANY_STATUSES, filters.company_status, "Todas"),
        ),
        ("Status das vagas", _label(_JOB_STATUSES, filters.job_status, "Todos")),
        (
            "Status das candidaturas",
            _label(_APPLICATION_STATUSES, filters.application_status, "Todos"),
        ),
        *((label, str(counts[key])) for key, label in _INDICATORS),
    ]


def _day(day: date | None) -> str:
    return brazilian_date(day) if day else _NO_DATE_LIMIT


def _label[Status: StrEnum](
    labels: Mapping[Status, str], value: Status | None, everything: str
) -> str:
    return labels[value] if value is not None else everything
