from collections.abc import Iterator
from datetime import date, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser, Company, Job, Skill
from app.db.models.enums import CompanyStatus, SkillType, UserType, WorkMode
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

ADMIN = {"Authorization": "Bearer administrator"}
CANDIDATE = {"Authorization": "Bearer candidate"}
COMPANY = {"Authorization": "Bearer company"}


class TrainingIdentityProvider(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token not in ("administrator", "candidate", "company"):
            raise InvalidAccessTokenError
        return f"training-{token}"


@pytest.fixture
def training_client(
    application: FastAPI, database_session: Session
) -> Iterator[TestClient]:
    users = [
        AppUser(
            email=f"training@{user_type.value}.example.invalid",
            identity_subject=f"training-{user_type.value}",
            user_type=user_type,
        )
        for user_type in (UserType.ADMINISTRATOR, UserType.CANDIDATE, UserType.COMPANY)
    ]
    database_session.add_all(users)
    database_session.flush()
    company_user = users[2]
    database_session.add(
        Company(
            id=company_user.id,
            cnpj="47960950000121",
            legal_name="Training Synthetic Company",
            corporate_email=company_user.email,
            primary_cnae="6201501",
            status=CompanyStatus.APPROVED,
        )
    )
    # Committed so a rolled-back request does not take the scenario with it; the
    # fixture still discards everything at the end.
    database_session.commit()
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = TrainingIdentityProvider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


@pytest.fixture
def skill_ids(database_session: Session) -> dict[str, UUID]:
    skills = {
        "excel": Skill(
            name="Zz Training Excel",
            normalized_name="zz training excel",
            type=SkillType.HARD,
        ),
        "escuta": Skill(
            name="Zz Training Escuta ativa",
            normalized_name="zz training escuta ativa",
            type=SkillType.SOFT,
        ),
    }
    database_session.add_all(skills.values())
    database_session.commit()
    return {key: skill.id for key, skill in skills.items()}


@pytest.fixture
def job_id(database_session: Session, training_client: TestClient) -> UUID:
    del training_client
    company_id = database_session.scalars(
        select(AppUser.id).where(AppUser.identity_subject == "training-company")
    ).one()
    job = Job(
        company_id=company_id,
        title="Zz Training Synthetic Job",
        description="Synthetic description.",
        work_mode=WorkMode.REMOTE,
        closing_date=date.today() + timedelta(days=30),
    )
    database_session.add(job)
    database_session.commit()
    return job.id
