import csv
import io
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.account_management.domain.account_export import ACCOUNT_EXPORT_HEADER
from app.account_management.services.account_filters import AccountFilters
from app.account_management.services.export_accounts import export_accounts
from app.core.csv_document import local_day
from app.db.models import AppUser, Candidate, Event
from tests.account_management.conftest import (
    ADMIN_TOKEN,
    BLOCKED_TOKEN,
    CANDIDATE_TOKEN,
    AccountManagementScenario,
    authorization,
)

pytestmark = pytest.mark.integration

LIST_PATH = "/api/v1/admin/accounts"
EXPORT_PATH = f"{LIST_PATH}/export"
BYTE_ORDER_MARK = b"\xef\xbb\xbf"
EMAIL_COLUMN = ACCOUNT_EXPORT_HEADER.index("E-mail")


def _export(client: TestClient, **params: str) -> Any:
    return client.get(EXPORT_PATH, params=params, headers=authorization(ADMIN_TOKEN))


def _rows(response: Any) -> list[list[str]]:
    content: bytes = response.content
    assert content.startswith(BYTE_ORDER_MARK)
    text = content.removeprefix(BYTE_ORDER_MARK).decode("utf-8")
    return list(csv.reader(io.StringIO(text, newline=""), delimiter=";"))


def _scenario_emails(session: Session, scenario: AccountManagementScenario) -> set[str]:
    ids = (
        scenario.complete_candidate_id,
        scenario.partial_candidate_id,
        scenario.no_resume_candidate_id,
        scenario.blocked_candidate_id,
        scenario.pending_company_id,
        scenario.approved_company_id,
    )
    return set(session.scalars(select(AppUser.email).where(AppUser.id.in_(ids))))


def _exports_by(session: Session, administrator_id: Any) -> list[Event]:
    return list(
        session.scalars(
            select(Event).where(
                Event.user_id == administrator_id,
                Event.event_type == "data_exported",
            )
        )
    )


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"account_status": "blocked"},
        {"user_type": "company"},
        {"company_status": "pending"},
        {"completeness": "incomplete"},
        {"user_type": "candidate", "min_completion": "30", "max_completion": "50"},
    ],
    ids=["all", "blocked", "companies", "pending", "incomplete", "completion"],
)
def test_export_holds_exactly_the_accounts_the_listing_shows(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
    params: dict[str, str],
) -> None:
    listing = account_management_client.get(
        LIST_PATH,
        params={**params, "limit": 100},
        headers=authorization(ADMIN_TOKEN),
    ).json()

    rows = _rows(_export(account_management_client, **params))

    ours = _scenario_emails(database_session, account_management_scenario)
    exported = [row[EMAIL_COLUMN] for row in rows[1:]]
    assert len(exported) == listing["total"]
    assert set(exported) & ours == {item["email"] for item in listing["items"]} & ours


def test_export_is_a_dated_excel_attachment_with_readable_columns(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
) -> None:
    response = _export(account_management_client)

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["cache-control"] == "no-store"
    assert re.fullmatch(
        r'attachment; filename="cadastros-\d{4}-\d{2}-\d{2}\.csv"',
        response.headers["content-disposition"],
    )
    rows = _rows(response)
    assert tuple(rows[0]) == ACCOUNT_EXPORT_HEADER
    by_email = {row[EMAIL_COLUMN]: row for row in rows[1:]}
    blocked = database_session.get(
        AppUser, account_management_scenario.blocked_candidate_id
    )
    company = database_session.get(
        AppUser, account_management_scenario.approved_company_id
    )
    assert blocked is not None and company is not None
    assert by_email[blocked.email] == [
        "Account Blocked Candidate",
        "Profissional",
        blocked.email,
        "Bloqueada",
        "",
        "Incompleto",
        "Cidade, Estado, Resumo profissional, Experiência profissional, "
        "Formação, Habilidades",
        local_day(blocked.created_at),
    ]
    assert by_email[company.email] == [
        "Account Approved Company",
        "Empresa",
        company.email,
        "Ativa",
        "Aprovada",
        "",
        "",
        local_day(company.created_at),
    ]


def test_export_without_matches_keeps_only_the_header(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    # Completeness applies to candidates only, so no company can match.
    rows = _rows(
        _export(account_management_client, user_type="company", completeness="complete")
    )

    assert rows == [list(ACCOUNT_EXPORT_HEADER)]


def test_a_name_typed_as_a_formula_is_exported_as_text(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
) -> None:
    candidate = database_session.get(
        Candidate, account_management_scenario.partial_candidate_id
    )
    assert candidate is not None
    candidate.full_name = '=HYPERLINK("https://attacker.invalid")'
    database_session.commit()

    rows = _rows(_export(account_management_client))

    assert [row[0] for row in rows[1:] if row[0].endswith('attacker.invalid")')] == [
        '\'=HYPERLINK("https://attacker.invalid")'
    ]


def test_export_is_logged_with_its_filters_but_never_its_values(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
) -> None:
    rows = _rows(
        _export(
            account_management_client, account_status="blocked", user_type="candidate"
        )
    )

    database_session.expire_all()
    events = _exports_by(database_session, account_management_scenario.administrator_id)
    assert len(events) == 1
    assert events[0].details == {
        "dataset": "accounts",
        "filters": {"user_type": "candidate", "account_status": "blocked"},
        "row_count": len(rows) - 1,
    }


@pytest.mark.parametrize(
    ("token", "status", "code"),
    [
        (None, 401, "invalid_access_token"),
        (CANDIDATE_TOKEN, 403, "administrator_required"),
        (BLOCKED_TOKEN, 403, "account_unavailable"),
    ],
)
def test_only_an_active_administrator_can_export(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
    token: str | None,
    status: int,
    code: str,
) -> None:
    exports = select(func.count(Event.id)).where(Event.event_type == "data_exported")
    before = database_session.scalar(exports)

    response = account_management_client.get(
        EXPORT_PATH, headers=authorization(token) if token else {}
    )

    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == code
    assert database_session.scalar(exports) == before


def test_an_export_whose_log_cannot_be_written_is_not_delivered(
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_commit() -> None:
        raise RuntimeError("synthetic commit failure")

    monkeypatch.setattr(database_session, "commit", fail_commit)

    with pytest.raises(RuntimeError):
        export_accounts(
            database_session,
            administrator_id=account_management_scenario.administrator_id,
            filters=AccountFilters(),
        )

    assert (
        _exports_by(database_session, account_management_scenario.administrator_id)
        == []
    )
