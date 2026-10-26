from datetime import UTC, datetime

from app.account_management.domain.account_export import (
    ACCOUNT_EXPORT_HEADER,
    account_export_row,
)
from app.db.models.enums import AccountStatus, CompanyStatus, UserType

CREATED = datetime(2026, 10, 2, 1, 30, tzinfo=UTC)


def test_header_names_the_columns_shown_on_the_accounts_screen() -> None:
    assert ACCOUNT_EXPORT_HEADER == (
        "Nome",
        "Tipo",
        "E-mail",
        "Status da conta",
        "Situação da empresa",
        "Currículo",
        "Campos faltantes",
        "Data de cadastro",
    )


def test_incomplete_candidate_lists_the_missing_fields() -> None:
    row = account_export_row(
        display_name="Maria Souza",
        user_type=UserType.CANDIDATE,
        email="maria@candidate.example.invalid",
        account_status=AccountStatus.BLOCKED,
        company_status=None,
        missing_fields=["city", "summary", "skills"],
        created_at=CREATED,
    )

    assert row == (
        "Maria Souza",
        "Profissional",
        "maria@candidate.example.invalid",
        "Bloqueada",
        "",
        "Incompleto",
        "Cidade, Resumo profissional, Habilidades",
        "01/10/2026",
    )


def test_complete_candidate_has_no_missing_fields() -> None:
    row = account_export_row(
        display_name="Maria Souza",
        user_type=UserType.CANDIDATE,
        email="maria@candidate.example.invalid",
        account_status=AccountStatus.ACTIVE,
        company_status=None,
        missing_fields=[],
        created_at=CREATED,
    )

    assert row[3:7] == ("Ativa", "", "Completo", "")


def test_company_leaves_the_resume_columns_blank() -> None:
    row = account_export_row(
        display_name=None,
        user_type=UserType.COMPANY,
        email="contato@company.example.invalid",
        account_status=AccountStatus.SUSPENDED,
        company_status=CompanyStatus.PENDING,
        missing_fields=None,
        created_at=CREATED,
    )

    assert row == (
        "",
        "Empresa",
        "contato@company.example.invalid",
        "Suspensa",
        "Pendente",
        "",
        "",
        "01/10/2026",
    )
