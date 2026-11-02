import csv
import io
import re
from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AppUser, Event
from app.db.models.enums import UserType
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from app.indicators.schemas.indicator_filters import IndicatorFilters
from app.indicators.services.export_indicators import export_indicators
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration

INDICATORS_PATH = "/api/v1/indicators"
EXPORT_PATH = f"{INDICATORS_PATH}/export"
ADMIN = {"Authorization": "Bearer admin"}
BYTE_ORDER_MARK = b"\xef\xbb\xbf"
# Dashboard keys and the rows that carry them in the CSV.
INDICATOR_LABELS = {
    "candidates": "Profissionais",
    "companies": "Empresas",
    "jobs": "Vagas",
    "applications": "Candidaturas",
    "matches": "Matches",
    "candidates_without_placement": "Profissionais sem colocação",
    "candidates_with_unknown_employment": "Situação profissional não informada",
    "incomplete_resumes": "Currículos incompletos",
}


class ExportIdentity(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token not in {"admin", "candidate"}:
            raise InvalidAccessTokenError
        return f"indicator-export-{token}"


@pytest.fixture
def administrator_id(database_session: Session) -> UUID:
    administrator = AppUser(
        email="admin@indicator-export.example.invalid",
        identity_subject="indicator-export-admin",
        user_type=UserType.ADMINISTRATOR,
    )
    database_session.add_all(
        (
            administrator,
            AppUser(
                email="candidate@indicator-export.example.invalid",
                identity_subject="indicator-export-candidate",
                user_type=UserType.CANDIDATE,
            ),
        )
    )
    database_session.commit()
    return administrator.id


@pytest.fixture
def export_client(
    application: FastAPI, database_session: Session, administrator_id: UUID
) -> Iterator[TestClient]:
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = ExportIdentity
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


def _rows(response: Any) -> dict[str, str]:
    content: bytes = response.content
    assert content.startswith(BYTE_ORDER_MARK)
    text = content.removeprefix(BYTE_ORDER_MARK).decode("utf-8")
    header, *rows = csv.reader(io.StringIO(text, newline=""), delimiter=";")
    assert header == ["Item", "Valor"]
    return dict((item, value) for item, value in rows)


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"start_date": "2026-01-01", "end_date": "2026-12-31"},
        {"account_status": "active", "job_status": "published"},
        {"candidate_availability": "available", "application_status": "applied"},
    ],
    ids=["unfiltered", "period", "statuses", "availability"],
)
def test_export_holds_the_numbers_the_dashboard_shows(
    export_client: TestClient, params: dict[str, str]
) -> None:
    dashboard = export_client.get(INDICATORS_PATH, params=params, headers=ADMIN).json()

    exported = _rows(export_client.get(EXPORT_PATH, params=params, headers=ADMIN))

    numbers = {**dashboard["totals"], **dashboard["segments"]}
    assert {key: exported[label] for key, label in INDICATOR_LABELS.items()} == {
        key: str(numbers[key]) for key in INDICATOR_LABELS
    }


def test_export_is_a_dated_excel_attachment_naming_its_filters(
    export_client: TestClient,
) -> None:
    response = export_client.get(
        EXPORT_PATH,
        params={"start_date": "2026-07-01", "company_status": "approved"},
        headers=ADMIN,
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["cache-control"] == "no-store"
    assert re.fullmatch(
        r'attachment; filename="relatorios-\d{4}-\d{2}-\d{2}\.csv"',
        response.headers["content-disposition"],
    )
    rows = _rows(response)
    assert re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", rows["Gerado em"])
    assert rows["Data inicial"] == "01/07/2026"
    assert rows["Data final"] == "Sem limite"
    assert rows["Situação da empresa"] == "Aprovada"
    assert rows["Status das contas"] == "Todos"


def test_export_is_logged_with_its_filters(
    export_client: TestClient, database_session: Session, administrator_id: UUID
) -> None:
    export_client.get(
        EXPORT_PATH,
        params={"end_date": "2026-10-31", "job_status": "published"},
        headers=ADMIN,
    )

    database_session.expire_all()
    events = database_session.scalars(
        select(Event).where(
            Event.user_id == administrator_id, Event.event_type == "data_exported"
        )
    ).all()
    assert [event.details for event in events] == [
        {
            "dataset": "indicators",
            "filters": {"end_date": "2026-10-31", "job_status": "published"},
            "row_count": 16,
        }
    ]


@pytest.mark.parametrize(
    ("headers", "params", "status", "code"),
    [
        ({}, {}, 401, "invalid_access_token"),
        ({"Authorization": "Bearer candidate"}, {}, 403, "administrator_required"),
        (
            ADMIN,
            {"start_date": "2026-10-02", "end_date": "2026-10-01"},
            422,
            "invalid_period",
        ),
    ],
)
def test_a_refused_export_writes_nothing(
    export_client: TestClient,
    database_session: Session,
    headers: dict[str, str],
    params: dict[str, str],
    status: int,
    code: str,
) -> None:
    exports = select(func.count(Event.id)).where(Event.event_type == "data_exported")
    before = database_session.scalar(exports)

    response = export_client.get(EXPORT_PATH, params=params, headers=headers)

    assert response.status_code == status
    assert response.json()["code"] == code
    assert database_session.scalar(exports) == before


def test_an_export_whose_log_cannot_be_written_is_not_delivered(
    database_session: Session,
    administrator_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_commit() -> None:
        raise RuntimeError("synthetic commit failure")

    monkeypatch.setattr(database_session, "commit", fail_commit)

    with pytest.raises(RuntimeError):
        export_indicators(
            database_session,
            administrator_id=administrator_id,
            filters=IndicatorFilters(),
        )

    assert (
        database_session.scalar(
            select(func.count(Event.id)).where(Event.user_id == administrator_id)
        )
        == 0
    )
