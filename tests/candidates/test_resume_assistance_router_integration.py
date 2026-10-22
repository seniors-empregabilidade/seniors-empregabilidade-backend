import os
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db.models import (
    Administrator,
    AppUser,
    Candidate,
    Education,
    Experience,
    Resume,
    ResumeGuidance,
    ResumeSkill,
    Skill,
)
from app.db.models.enums import SkillType, UserType
from app.db.session import get_session_factory
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

LIST_PATH = "/api/v1/professionals"
SUBJECTS = [
    f"us08-{role}" for role in ("admin", "empty", "complete", "contacted", "company")
]
SKILL_NAME = "US08 synthetic skill"


class AssistanceIdentityProvider(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token not in {"admin", "empty", "complete", "contacted", "company"}:
            raise InvalidAccessTokenError
        return f"us08-{token}"


def auth(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {role}"}


def fixture_items(
    items: list[dict[str, Any]], actors: dict[str, UUID]
) -> list[dict[str, Any]]:
    fixture_ids = {str(actors[role]) for role in ("empty", "complete", "contacted")}
    return [item for item in items if item["id"] in fixture_ids]


@pytest.fixture
def actors(application: FastAPI) -> Iterator[dict[str, UUID]]:
    application.dependency_overrides[get_identity_provider] = AssistanceIdentityProvider
    factory = get_session_factory()
    with factory.begin() as session:
        users = {
            role: AppUser(
                email=f"us08-{role}@example.invalid",
                identity_subject=f"us08-{role}",
                user_type=UserType.ADMINISTRATOR
                if role == "admin"
                else UserType.COMPANY
                if role == "company"
                else UserType.CANDIDATE,
            )
            for role in ("admin", "empty", "complete", "contacted", "company")
        }
        session.add_all(users.values())
        session.flush()
        session.add(Administrator(id=users["admin"].id, full_name="Synthetic Admin"))
        for role, name in (
            ("empty", "A Empty Resume"),
            ("complete", "B Complete Resume"),
            ("contacted", "C Contacted Resume"),
        ):
            session.add(
                Candidate(
                    id=users[role].id,
                    full_name=name,
                    cpf=f"{users[role].id.int % 10**11:011d}",
                    birth_date=date(1968, 3, 15),
                    phone="51999990000",
                    city="Porto Alegre" if role == "complete" else None,
                    state="RS" if role == "complete" else None,
                )
            )
        session.flush()
        resume = Resume(
            candidate_id=users["complete"].id,
            summary="Experienced professional",
        )
        session.add(resume)
        session.flush()
        session.add(
            Experience(
                resume_id=resume.id,
                company_name="Synthetic Company",
                role="Analyst",
                start_date=date(2010, 1, 1),
            )
        )
        session.add(Education(resume_id=resume.id, institution="Synthetic School"))
        skill = Skill(
            name=SKILL_NAME,
            normalized_name=SKILL_NAME.casefold(),
            type=SkillType.SOFT,
        )
        session.add(skill)
        session.flush()
        session.add(ResumeSkill(resume_id=resume.id, skill_id=skill.id))
        session.add_all(
            [
                ResumeGuidance(
                    candidate_id=users["contacted"].id,
                    administrator_id=users["admin"].id,
                    note=note,
                    created_at=datetime(2026, 10, day, tzinfo=UTC),
                )
                for day, note in ((1, "First contact"), (2, "Latest guidance"))
            ]
        )
        ids = {role: user.id for role, user in users.items()}
    yield ids
    with factory.begin() as session:
        session.execute(
            delete(ResumeGuidance).where(
                ResumeGuidance.administrator_id == ids["admin"]
            )
        )
        session.execute(delete(AppUser).where(AppUser.identity_subject.in_(SUBJECTS)))
        session.execute(delete(Skill).where(Skill.name == SKILL_NAME))


def test_admin_list_matches_the_frontend_contract(
    client: TestClient, actors: dict[str, UUID]
) -> None:
    response = client.get(LIST_PATH, headers=auth("admin"))

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    items = fixture_items(response.json(), actors)
    assert [item["full_name"] for item in items] == [
        "A Empty Resume",
        "B Complete Resume",
        "C Contacted Resume",
    ]
    assert set(items[0]) == {
        "id",
        "full_name",
        "email",
        "phone",
        "city",
        "state",
        "missing_fields",
        "last_guidance",
    }
    assert items[0]["missing_fields"] == [
        "city",
        "state",
        "summary",
        "experiences",
        "education",
        "skills",
    ]
    assert items[1]["missing_fields"] == []
    assert items[2]["last_guidance"]["note"] == "Latest guidance"
    assert items[2]["last_guidance"]["administrator_name"] == "Synthetic Admin"
    assert items[0]["last_guidance"] is None


@pytest.mark.parametrize(
    ("query", "expected_names"),
    [
        ("completeness=complete", ["B Complete Resume"]),
        ("completeness=incomplete", ["A Empty Resume", "C Contacted Resume"]),
        ("contact_status=contacted", ["C Contacted Resume"]),
        ("contact_status=not_contacted", ["A Empty Resume", "B Complete Resume"]),
        (
            "completeness=incomplete&contact_status=contacted",
            ["C Contacted Resume"],
        ),
    ],
)
def test_admin_filters_and_paginates_after_filtering(
    client: TestClient, actors: dict[str, UUID], query: str, expected_names: list[str]
) -> None:
    response = client.get(f"{LIST_PATH}?{query}", headers=auth("admin"))

    assert response.status_code == 200
    assert [
        item["full_name"] for item in fixture_items(response.json(), actors)
    ] == expected_names


def test_admin_paginates_after_filtering(
    client: TestClient, actors: dict[str, UUID]
) -> None:
    base = f"{LIST_PATH}?completeness=incomplete"
    all_items = client.get(base, headers=auth("admin")).json()
    page = client.get(f"{base}&limit=1&offset=1", headers=auth("admin"))

    assert page.status_code == 200
    assert [item["id"] for item in page.json()] == [all_items[1]["id"]]


def test_candidate_and_admin_see_the_same_pending_fields(
    client: TestClient, actors: dict[str, UUID]
) -> None:
    candidate = client.get(f"{LIST_PATH}/me", headers=auth("contacted"))
    admin = client.get(LIST_PATH, headers=auth("admin"))

    assert candidate.status_code == 200
    summaries = fixture_items(admin.json(), actors)
    assert candidate.json()["missing_fields"] == summaries[2]["missing_fields"]


@pytest.mark.parametrize("role", ["empty", "company"])
def test_list_rejects_non_administrators(
    client: TestClient, actors: dict[str, UUID], role: str
) -> None:
    response = client.get(LIST_PATH, headers=auth(role))

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "administrator_required"


def test_list_requires_authentication(
    client: TestClient, actors: dict[str, UUID]
) -> None:
    response = client.get(LIST_PATH)

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.parametrize("query", ["completeness=unknown", "limit=0", "offset=-1"])
def test_list_rejects_invalid_filters(
    client: TestClient, actors: dict[str, UUID], query: str
) -> None:
    response = client.get(f"{LIST_PATH}?{query}", headers=auth("admin"))

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_admin_records_guidance_with_server_owned_metadata(
    client: TestClient, actors: dict[str, UUID]
) -> None:
    path = f"{LIST_PATH}/{actors['empty']}/guidance"

    response = client.post(
        path,
        json={"note": "  Complete your résumé summary.  "},
        headers=auth("admin"),
    )

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    assert set(response.json()) == {"id", "note", "created_at", "administrator_name"}
    assert response.json()["note"] == "Complete your résumé summary."
    assert response.json()["administrator_name"] == "Synthetic Admin"
    assert datetime.fromisoformat(response.json()["created_at"]).tzinfo is not None
    with get_session_factory()() as session:
        stored = session.scalar(
            select(ResumeGuidance).where(ResumeGuidance.candidate_id == actors["empty"])
        )
        assert stored is not None
        assert stored.administrator_id == actors["admin"]
        assert stored.note == response.json()["note"]
    listed = client.get(f"{LIST_PATH}?contact_status=contacted", headers=auth("admin"))
    assert [item["full_name"] for item in fixture_items(listed.json(), actors)] == [
        "A Empty Resume",
        "C Contacted Resume",
    ]
    assert fixture_items(listed.json(), actors)[0]["last_guidance"] == response.json()
    candidate = client.get(f"{LIST_PATH}/me", headers=auth("empty"))
    assert "last_guidance" not in candidate.json()
    assert "note" not in candidate.json()


def test_guidance_is_append_only_and_newest_entry_is_listed(
    client: TestClient, actors: dict[str, UUID]
) -> None:
    path = f"{LIST_PATH}/{actors['contacted']}/guidance"

    response = client.post(
        path, json={"note": "Follow-up guidance"}, headers=auth("admin")
    )

    assert response.status_code == 201
    with get_session_factory()() as session:
        count = session.scalar(
            select(func.count())
            .select_from(ResumeGuidance)
            .where(ResumeGuidance.candidate_id == actors["contacted"])
        )
    assert count == 3
    listed = client.get(LIST_PATH, headers=auth("admin"))
    assert fixture_items(listed.json(), actors)[2]["last_guidance"] == response.json()


@pytest.mark.parametrize(
    "body",
    [
        {"note": ""},
        {"note": "   "},
        {"note": "x" * 2001},
        {"note": "Valid", "administrator_id": str(uuid4())},
    ],
)
def test_invalid_guidance_creates_no_record(
    client: TestClient, actors: dict[str, UUID], body: dict[str, str]
) -> None:
    response = client.post(
        f"{LIST_PATH}/{actors['empty']}/guidance",
        json=body,
        headers=auth("admin"),
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "validation_error"
    with get_session_factory()() as session:
        count = session.scalar(
            select(func.count())
            .select_from(ResumeGuidance)
            .where(ResumeGuidance.candidate_id == actors["empty"])
        )
    assert count == 0


def test_unknown_professional_returns_stable_not_found(
    client: TestClient, actors: dict[str, UUID]
) -> None:
    response = client.post(
        f"{LIST_PATH}/{uuid4()}/guidance",
        json={"note": "Synthetic guidance"},
        headers=auth("admin"),
    )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "professional_not_found"


@pytest.mark.parametrize("role", ["empty", "company"])
def test_guidance_rejects_non_administrators(
    client: TestClient, actors: dict[str, UUID], role: str
) -> None:
    response = client.post(
        f"{LIST_PATH}/{actors['contacted']}/guidance",
        json={"note": "Synthetic guidance"},
        headers=auth(role),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "administrator_required"


def test_guidance_requires_authentication(
    client: TestClient, actors: dict[str, UUID]
) -> None:
    response = client.post(
        f"{LIST_PATH}/{actors['contacted']}/guidance",
        json={"note": "Synthetic guidance"},
    )

    assert response.status_code == 401
