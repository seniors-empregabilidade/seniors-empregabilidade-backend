from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.local_date import to_local_date
from app.db.models import (
    AppUser,
    Candidate,
    Company,
    Job,
    JobSkill,
    Resume,
    ResumeSkill,
    Skill,
)
from app.db.models.enums import (
    CompanyStatus,
    JobStatus,
    SkillType,
    UserType,
    WorkMode,
)
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration

JOBS_PATH = "/api/v1/jobs"
FAR_FUTURE = date(2099, 12, 31)


class SearchIdentityProvider(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token not in {"candidate", "candidate-without-resume", "company"}:
            raise InvalidAccessTokenError
        return f"job-search-{token}"


@dataclass(frozen=True, slots=True)
class SearchScenario:
    marker: str
    """Present in every scenario title, so searches ignore other stored jobs."""
    python_id: UUID
    excel_id: UUID
    forklift_id: UUID
    full_match_id: UUID
    """Requires Python and Excel, both on the candidate's résumé."""
    partial_match_id: UUID
    """Requires Python and Forklift; the candidate only has Python."""
    no_match_id: UUID
    """Requires Forklift only, published today and closing today."""
    no_skills_id: UUID
    """Requires no skill and has no publication date."""
    hidden_ids: tuple[UUID, ...]
    """Draft, under review, paused, expired, closed, or past its closing date."""


@pytest.fixture
def scenario(database_session: Session) -> SearchScenario:
    marker = f"jobsearch{uuid4().hex[:10]}"
    now = datetime.now(UTC)
    today = to_local_date(now)

    candidate = AppUser(
        email=f"{marker}-candidate@candidate.example.invalid",
        identity_subject="job-search-candidate",
        user_type=UserType.CANDIDATE,
    )
    candidate_without_resume = AppUser(
        email=f"{marker}-no-resume@candidate.example.invalid",
        identity_subject="job-search-candidate-without-resume",
        user_type=UserType.CANDIDATE,
    )
    acme_user = AppUser(
        email=f"{marker}@acme.example.invalid",
        identity_subject="job-search-company",
        user_type=UserType.COMPANY,
    )
    beta_user = AppUser(
        email=f"{marker}@beta.example.invalid",
        identity_subject=None,
        user_type=UserType.COMPANY,
    )
    database_session.add_all(
        (candidate, candidate_without_resume, acme_user, beta_user)
    )
    database_session.flush()

    database_session.add_all(
        [
            Candidate(
                id=user.id,
                full_name="Synthetic Job Seeker",
                cpf=f"{uuid4().int % 10**11:011d}",
                birth_date=date(1970, 1, 1),
                phone="+5551999990000",
            )
            for user in (candidate, candidate_without_resume)
        ]
    )
    database_session.add_all(
        [
            Company(
                id=acme_user.id,
                cnpj=f"{uuid4().int % 10**14:014d}",
                legal_name="Acme Synthetic Staffing Ltd.",
                trade_name="Acme Synthetic Staffing",
                corporate_email=acme_user.email,
                status=CompanyStatus.APPROVED,
            ),
            Company(
                id=beta_user.id,
                cnpj=f"{uuid4().int % 10**14:014d}",
                legal_name="Beta Synthetic Logistics Ltd.",
                corporate_email=beta_user.email,
                status=CompanyStatus.APPROVED,
            ),
        ]
    )
    python, excel, forklift = (
        Skill(name=f"{marker} {name}", normalized_name=f"{marker} {name}", type=kind)
        for name, kind in (
            ("python", SkillType.HARD),
            ("excel", SkillType.HARD),
            ("forklift", SkillType.HARD),
        )
    )
    database_session.add_all((python, excel, forklift))
    database_session.flush()

    resume = Resume(candidate_id=candidate.id)
    database_session.add(resume)
    database_session.flush()
    database_session.add_all(
        ResumeSkill(resume_id=resume.id, skill_id=skill.id) for skill in (python, excel)
    )

    def job(
        title: str,
        *,
        company: AppUser = acme_user,
        status: JobStatus = JobStatus.PUBLISHED,
        closing_date: date = FAR_FUTURE,
        published_at: datetime | None = None,
        **columns: Any,
    ) -> Job:
        return Job(
            company_id=company.id,
            title=f"{marker} {title}",
            description="Synthetic job for search tests.",
            work_mode=columns.pop("work_mode", WorkMode.REMOTE),
            status=status,
            closing_date=closing_date,
            published_at=published_at,
            **columns,
        )

    full_match = job(
        "Analyst Senior",
        published_at=now - timedelta(days=3),
        location="Porto Alegre",
        salary_max=Decimal("9000.00"),
        work_mode=WorkMode.ONSITE,
    )
    partial_match = job(
        "Analyst Junior", company=beta_user, published_at=now - timedelta(days=1)
    )
    no_match = job("Warehouse Lead", published_at=now, closing_date=today)
    no_skills = job("Receptionist")
    hidden = [
        job("Analyst Draft", status=JobStatus.DRAFT),
        job("Analyst Reviewed", status=JobStatus.UNDER_REVIEW),
        job("Analyst Paused", status=JobStatus.PAUSED),
        job("Analyst Expired", status=JobStatus.EXPIRED),
        job("Analyst Closed", status=JobStatus.CLOSED),
        job("Analyst Late", closing_date=today - timedelta(days=1)),
    ]
    database_session.add_all([full_match, partial_match, no_match, no_skills, *hidden])
    database_session.flush()

    database_session.add_all(
        JobSkill(job_id=job.id, skill_id=skill.id)
        for job, skills in (
            (full_match, (python, excel)),
            (partial_match, (python, forklift)),
            (no_match, (forklift,)),
            *((hidden_job, (python,)) for hidden_job in hidden),
        )
        for skill in skills
    )
    database_session.flush()

    return SearchScenario(
        marker=marker,
        python_id=python.id,
        excel_id=excel.id,
        forklift_id=forklift.id,
        full_match_id=full_match.id,
        partial_match_id=partial_match.id,
        no_match_id=no_match.id,
        no_skills_id=no_skills.id,
        hidden_ids=tuple(hidden_job.id for hidden_job in hidden),
    )


@pytest.fixture
def search_client(
    application: FastAPI, database_session: Session, scenario: SearchScenario
) -> Iterator[TestClient]:
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = SearchIdentityProvider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


def search(
    client: TestClient, token: str = "candidate", **params: str | int
) -> list[dict[str, Any]]:
    response = client.get(
        JOBS_PATH, params=params, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    return list(response.json())


def ids(results: list[dict[str, Any]]) -> list[str]:
    return [result["id"] for result in results]


def test_open_jobs_come_most_compatible_first(
    search_client: TestClient, scenario: SearchScenario
) -> None:
    results = search(search_client, search=scenario.marker)

    assert ids(results) == [
        str(scenario.full_match_id),
        str(scenario.partial_match_id),
        str(scenario.no_match_id),
        str(scenario.no_skills_id),
    ]


def test_each_job_tells_how_many_requirements_the_candidate_meets(
    search_client: TestClient, scenario: SearchScenario
) -> None:
    results = {
        result["id"]: result for result in search(search_client, search=scenario.marker)
    }

    full = results[str(scenario.full_match_id)]
    assert (full["matched_skill_count"], full["required_skill_count"]) == (2, 2)
    assert full["missing_skills"] == []

    partial = results[str(scenario.partial_match_id)]
    assert (partial["matched_skill_count"], partial["required_skill_count"]) == (1, 2)
    assert partial["missing_skills"] == [
        {
            "id": str(scenario.forklift_id),
            "name": f"{scenario.marker} forklift",
            "type": SkillType.HARD.value,
        }
    ]

    no_skills = results[str(scenario.no_skills_id)]
    assert (no_skills["matched_skill_count"], no_skills["required_skill_count"]) == (
        0,
        0,
    )
    assert no_skills["missing_skills"] == []


def test_a_candidate_without_resume_meets_no_requirement(
    search_client: TestClient, scenario: SearchScenario
) -> None:
    results = search(
        search_client, token="candidate-without-resume", search=scenario.marker
    )

    # Without a match to rank by, the most recently published job comes first.
    assert ids(results) == [
        str(scenario.no_match_id),
        str(scenario.partial_match_id),
        str(scenario.full_match_id),
        str(scenario.no_skills_id),
    ]
    assert [result["matched_skill_count"] for result in results] == [0, 0, 0, 0]
    full = results[2]
    assert [skill["id"] for skill in full["missing_skills"]] == [
        str(scenario.excel_id),
        str(scenario.python_id),
    ]


def test_each_job_carries_its_listing_data_and_nothing_private(
    search_client: TestClient, scenario: SearchScenario
) -> None:
    results = {
        result["id"]: result for result in search(search_client, search=scenario.marker)
    }

    full = results[str(scenario.full_match_id)]
    assert set(full) == {
        "id",
        "title",
        "company_name",
        "location",
        "work_mode",
        "salary_max",
        "published_at",
        "days_since_published",
        "matched_skill_count",
        "required_skill_count",
        "missing_skills",
    }
    assert full["title"] == f"{scenario.marker} Analyst Senior"
    assert full["company_name"] == "Acme Synthetic Staffing"
    assert full["location"] == "Porto Alegre"
    assert full["work_mode"] == WorkMode.ONSITE.value
    assert full["salary_max"] == "9000.00"
    assert full["days_since_published"] == 3

    partial = results[str(scenario.partial_match_id)]
    assert partial["company_name"] == "Beta Synthetic Logistics Ltd."
    assert partial["days_since_published"] == 1
    assert results[str(scenario.no_match_id)]["days_since_published"] == 0

    no_skills = results[str(scenario.no_skills_id)]
    assert no_skills["location"] is None
    assert no_skills["salary_max"] is None
    assert no_skills["published_at"] is None
    assert no_skills["days_since_published"] is None


def test_title_search_is_partial_and_ignores_case(
    search_client: TestClient, scenario: SearchScenario
) -> None:
    results = search(search_client, search=f"  {scenario.marker} ANALYST ".upper())

    assert ids(results) == [
        str(scenario.full_match_id),
        str(scenario.partial_match_id),
    ]


def test_a_search_without_matching_titles_finds_nothing(
    search_client: TestClient, scenario: SearchScenario
) -> None:
    assert search(search_client, search=f"{scenario.marker} astronaut") == []


@pytest.mark.parametrize("wildcard", ["%", "_"])
def test_like_wildcards_are_searched_literally(
    search_client: TestClient, scenario: SearchScenario, wildcard: str
) -> None:
    assert search(search_client, search=f"{scenario.marker}{wildcard}") == []


def test_a_search_with_a_nul_character_finds_nothing(
    search_client: TestClient, scenario: SearchScenario
) -> None:
    assert search(search_client, search=f"{scenario.marker}\x00") == []


@pytest.mark.parametrize("params", [{}, {"search": "   "}], ids=["absent", "blank"])
def test_without_a_search_term_every_open_job_is_listed(
    search_client: TestClient, scenario: SearchScenario, params: dict[str, str]
) -> None:
    listed: list[str] = []
    while page := search(search_client, **params, limit=100, offset=len(listed)):
        listed.extend(ids(page))

    open_ids = {
        scenario.full_match_id,
        scenario.partial_match_id,
        scenario.no_match_id,
        scenario.no_skills_id,
    }
    assert {str(job_id) for job_id in open_ids} <= set(listed)
    assert not {str(job_id) for job_id in scenario.hidden_ids} & set(listed)
    assert len(listed) == len(set(listed))


@pytest.mark.parametrize(
    ("limit", "offset", "expected"),
    [
        (2, 0, ["full_match_id", "partial_match_id"]),
        (4, 0, ["full_match_id", "partial_match_id", "no_match_id", "no_skills_id"]),
        (2, 2, ["no_match_id", "no_skills_id"]),
        (2, 3, ["no_skills_id"]),
        (2, 4, []),
    ],
    ids=[
        "first-page",
        "exactly-limit",
        "last-full-page",
        "last-partial-page",
        "past-end",
    ],
)
def test_pages_follow_the_same_order(
    search_client: TestClient,
    scenario: SearchScenario,
    limit: int,
    offset: int,
    expected: list[str],
) -> None:
    results = search(search_client, search=scenario.marker, limit=limit, offset=offset)

    assert ids(results) == [str(getattr(scenario, name)) for name in expected]


def test_ties_are_broken_by_id(
    search_client: TestClient, database_session: Session, scenario: SearchScenario
) -> None:
    company_id = database_session.get_one(Job, scenario.no_skills_id).company_id
    published_at = datetime(2026, 1, 1, tzinfo=UTC)
    twins = [
        Job(
            company_id=company_id,
            title=f"{scenario.marker} Twin Clerk",
            description="Synthetic twin job.",
            work_mode=WorkMode.HYBRID,
            status=JobStatus.PUBLISHED,
            closing_date=FAR_FUTURE,
            published_at=published_at,
        )
        for _ in range(3)
    ]
    database_session.add_all(twins)
    database_session.flush()

    results = search(search_client, search=f"{scenario.marker} twin")

    assert ids(results) == sorted(str(twin.id) for twin in twins)


def test_results_are_not_cached(
    search_client: TestClient, scenario: SearchScenario
) -> None:
    response = search_client.get(
        JOBS_PATH,
        params={"search": scenario.marker},
        headers={"Authorization": "Bearer candidate"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("token", "status", "code"),
    [(None, 401, "invalid_access_token"), ("company", 403, "candidate_required")],
    ids=["anonymous", "company"],
)
def test_only_candidates_can_search(
    search_client: TestClient,
    scenario: SearchScenario,
    token: str | None,
    status: int,
    code: str,
) -> None:
    response = search_client.get(
        JOBS_PATH, headers={"Authorization": f"Bearer {token}"} if token else {}
    )

    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == code
