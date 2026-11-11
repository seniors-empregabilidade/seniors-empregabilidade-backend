from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AppUser, Company, Job
from app.db.models.enums import CompanyStatus, JobStatus, UserType, WorkMode
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration

PATH = "/api/v1/admin/jobs"
MARKER = "Zz Admin Jobs"
ADMIN = {"Authorization": "Bearer administrator"}
CANDIDATE = {"Authorization": "Bearer candidate"}
COMPANY = {"Authorization": "Bearer company"}


class AdminJobsIdentityProvider(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token not in ("administrator", "candidate", "company"):
            raise InvalidAccessTokenError
        return f"admin-jobs-{token}"


@pytest.fixture
def admin_jobs_client(
    application: FastAPI, database_session: Session
) -> Iterator[TestClient]:
    users = {
        name: AppUser(
            email=f"admin-jobs-{name}@synthetic.example.invalid",
            identity_subject=f"admin-jobs-{name}",
            user_type=user_type,
        )
        for name, user_type in (
            ("administrator", UserType.ADMINISTRATOR),
            ("candidate", UserType.CANDIDATE),
            ("company", UserType.COMPANY),
            ("other-company", UserType.COMPANY),
        )
    }
    database_session.add_all(users.values())
    database_session.flush()
    with_trade_name = Company(
        id=users["company"].id,
        cnpj="11222333000181",
        legal_name="Zz Admin Jobs Empresa Ltda.",
        trade_name="Zz Nome Fantasia",
        corporate_email=users["company"].email,
        primary_cnae="6201501",
        status=CompanyStatus.APPROVED,
    )
    without_trade_name = Company(
        id=users["other-company"].id,
        cnpj="11444777000161",
        legal_name="Zz Razao Social Ltda.",
        corporate_email=users["other-company"].email,
        primary_cnae="6201501",
        status=CompanyStatus.APPROVED,
    )
    database_session.add_all([with_trade_name, without_trade_name])
    closing_date = date.today() + timedelta(days=30)
    database_session.add_all(
        [
            Job(
                company_id=with_trade_name.id,
                title=f"{MARKER} Coordenador",
                description="Synthetic description.",
                work_mode=WorkMode.ONSITE,
                closing_date=closing_date,
                status=JobStatus.CLOSED,
            ),
            Job(
                company_id=with_trade_name.id,
                title=f"{MARKER} Analista",
                description="Synthetic description.",
                work_mode=WorkMode.REMOTE,
                closing_date=closing_date,
                status=JobStatus.PUBLISHED,
            ),
            Job(
                company_id=without_trade_name.id,
                title=f"{MARKER} Assistente",
                description="Synthetic description.",
                work_mode=WorkMode.HYBRID,
                closing_date=closing_date,
                status=JobStatus.DRAFT,
            ),
        ]
    )
    # Committed so a rolled-back request does not take the scenario with it; the
    # database fixture still discards everything at the end.
    database_session.commit()
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = AdminJobsIdentityProvider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


@pytest.mark.parametrize("headers", [CANDIDATE, COMPANY])
def test_only_administrators_list_jobs(
    admin_jobs_client: TestClient, headers: dict[str, str]
) -> None:
    response = admin_jobs_client.get(PATH, headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "administrator_required"


def test_listing_jobs_requires_authentication(admin_jobs_client: TestClient) -> None:
    response = admin_jobs_client.get(PATH)

    assert response.status_code == 401


def test_search_matches_part_of_the_title_in_any_status_ordered_by_title(
    admin_jobs_client: TestClient,
) -> None:
    response = admin_jobs_client.get(
        PATH, params={"search": "zZ ADMIN jobs"}, headers=ADMIN
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["total"] == 3
    assert [
        {key: item[key] for key in ("title", "company_name", "status")}
        for item in body["items"]
    ] == [
        {
            "title": f"{MARKER} Analista",
            "company_name": "Zz Nome Fantasia",
            "status": "published",
        },
        {
            "title": f"{MARKER} Assistente",
            "company_name": "Zz Razao Social Ltda.",
            "status": "draft",
        },
        {
            "title": f"{MARKER} Coordenador",
            "company_name": "Zz Nome Fantasia",
            "status": "closed",
        },
    ]
    assert all(
        set(item) == {"id", "title", "company_name", "status"} for item in body["items"]
    )


def test_a_page_keeps_the_total_of_every_matching_job(
    admin_jobs_client: TestClient,
) -> None:
    response = admin_jobs_client.get(
        PATH, params={"search": MARKER, "limit": 2, "offset": 1}, headers=ADMIN
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert [item["title"] for item in body["items"]] == [
        f"{MARKER} Assistente",
        f"{MARKER} Coordenador",
    ]


@pytest.mark.parametrize("search", [f"{MARKER}%", f"{MARKER}_", "\x00"])
def test_wildcards_and_nul_characters_find_nothing(
    admin_jobs_client: TestClient, search: str
) -> None:
    response = admin_jobs_client.get(PATH, params={"search": search}, headers=ADMIN)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_a_search_longer_than_a_job_title_is_rejected(
    admin_jobs_client: TestClient,
) -> None:
    response = admin_jobs_client.get(PATH, params={"search": "x" * 151}, headers=ADMIN)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
