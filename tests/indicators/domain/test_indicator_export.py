from datetime import UTC, date, datetime

from app.db.models.enums import (
    AccountStatus,
    ApplicationStatus,
    AvailabilityStatus,
    CompanyStatus,
    JobStatus,
)
from app.indicators.domain.indicator_export import (
    INDICATOR_EXPORT_HEADER,
    indicator_export_rows,
)
from app.indicators.schemas.indicator_filters import IndicatorFilters

GENERATED = datetime(2026, 10, 2, 1, 30, tzinfo=UTC)
COUNTS = {
    "candidates": 412,
    "companies": 86,
    "jobs": 40,
    "applications": 1104,
    "matches": 27,
    "candidates_without_placement": 12,
    "candidates_with_unknown_employment": 3,
    "incomplete_resumes": 74,
}
INDICATOR_ROWS = [
    ("Profissionais", "412"),
    ("Empresas", "86"),
    ("Vagas", "40"),
    ("Candidaturas", "1104"),
    ("Matches", "27"),
    ("Profissionais sem colocação", "12"),
    ("Situação profissional não informada", "3"),
    ("Currículos incompletos", "74"),
]


def test_unfiltered_export_states_that_nothing_was_filtered() -> None:
    rows = indicator_export_rows(
        generated_at=GENERATED, filters=IndicatorFilters(), counts=COUNTS
    )

    assert INDICATOR_EXPORT_HEADER == ("Item", "Valor")
    assert rows == [
        ("Gerado em", "01/10/2026 22:30"),
        ("Data inicial", "Sem limite"),
        ("Data final", "Sem limite"),
        ("Status das contas", "Todos"),
        ("Disponibilidade do profissional", "Todas"),
        ("Situação da empresa", "Todas"),
        ("Status das vagas", "Todos"),
        ("Status das candidaturas", "Todos"),
        *INDICATOR_ROWS,
    ]


def test_filtered_export_names_every_applied_filter() -> None:
    filters = IndicatorFilters(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 19),
        account_status=AccountStatus.BLOCKED,
        candidate_availability=AvailabilityStatus.UNAVAILABLE,
        company_status=CompanyStatus.APPROVED,
        job_status=JobStatus.UNDER_REVIEW,
        application_status=ApplicationStatus.IN_SELECTION_PROCESS,
    )

    rows = indicator_export_rows(generated_at=GENERATED, filters=filters, counts=COUNTS)

    assert rows[1:8] == [
        ("Data inicial", "01/07/2026"),
        ("Data final", "19/08/2026"),
        ("Status das contas", "Bloqueadas"),
        ("Disponibilidade do profissional", "Indisponível"),
        ("Situação da empresa", "Aprovada"),
        ("Status das vagas", "Em revisão"),
        ("Status das candidaturas", "Em seleção"),
    ]
    assert rows[8:] == INDICATOR_ROWS
