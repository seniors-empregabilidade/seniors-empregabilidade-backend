from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import ClassVar
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.models import (
    Application,
    AppUser,
    Candidate,
    Company,
    Job,
    JobSkill,
    Skill,
)
from app.db.models.enums import ApplicationStatus, JobStatus, UserType
from app.db.session import get_session_factory
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

OWNER_TOKEN = "applications-owner"
OTHER_TOKEN = "applications-other"


class ApplicationsIdentityProvider(FakeIdentityProvider):
    """Maps a fixed set of synthetic bearer tokens to distinct subjects."""

    _SUBJECTS_BY_TOKEN: ClassVar[dict[str, str]] = {
        OWNER_TOKEN: "subject-applications-owner",
        OTHER_TOKEN: "subject-applications-other",
    }

    def verify_access_token(self, token: str) -> str:
        try:
            return self._SUBJECTS_BY_TOKEN[token]
        except KeyError:
            raise InvalidAccessTokenError from None


@pytest.fixture
def identity_provider() -> ApplicationsIdentityProvider:
    return ApplicationsIdentityProvider()


@pytest.fixture
def applications_client(
    application: FastAPI,
    client: TestClient,
    identity_provider: ApplicationsIdentityProvider,
) -> Iterator[TestClient]:
    application.dependency_overrides[get_identity_provider] = lambda: identity_provider
    yield client
    application.dependency_overrides.clear()


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass(frozen=True, slots=True)
class ApplicationsScenario:
    now: datetime
    owner_id: UUID
    other_id: UUID
    company_acme_id: UUID
    company_beta_id: UUID
    job_target_id: UUID
    """Job behind the NOT_SELECTED application; shares skills with the
    "similar" jobs and none with `job_no_match_id`."""
    job_similar_strong_id: UUID
    """Published, shares both skills with `job_target_id`, never applied to."""
    job_similar_weak_id: UUID
    """Published, shares one skill with `job_target_id`, never applied to."""
    job_no_match_id: UUID
    """Published, shares no skill with `job_target_id`."""
    job_already_applied_id: UUID
    """Shares both skills with `job_target_id` but the owner already applied
    to it, so it must never appear as a suggestion."""
    job_draft_id: UUID
    """Shares both skills with `job_target_id` but is not published, so it
    must never appear as a suggestion."""
    job_active_id: UUID
    """Hosted by the Beta company; backs the owner's still-active application."""
    job_withdrawn_id: UUID
    """Hosted by the Acme company; backs the owner's already-withdrawn
    application, kept separate from the skill-matching jobs above."""
    application_not_selected_id: UUID
    application_active_id: UUID
    application_withdrawn_id: UUID
    application_on_already_applied_job_id: UUID
    application_other_candidate_id: UUID


@pytest.fixture
def scenario() -> Iterator[ApplicationsScenario]:
    now = datetime.now(UTC)
    factory = get_session_factory()
    user_ids: list[UUID] = []
    skill_ids: list[UUID] = []

    with factory.begin() as session:
        owner = AppUser(
            email="applications-owner@synthetic.example.invalid",
            identity_subject=ApplicationsIdentityProvider._SUBJECTS_BY_TOKEN[
                OWNER_TOKEN
            ],
            user_type=UserType.CANDIDATE,
        )
        other = AppUser(
            email="applications-other@synthetic.example.invalid",
            identity_subject=ApplicationsIdentityProvider._SUBJECTS_BY_TOKEN[
                OTHER_TOKEN
            ],
            user_type=UserType.CANDIDATE,
        )
        company_acme_user = AppUser(
            email="applications-acme@synthetic.example.invalid",
            identity_subject=None,
            user_type=UserType.COMPANY,
        )
        company_beta_user = AppUser(
            email="applications-beta@synthetic.example.invalid",
            identity_subject=None,
            user_type=UserType.COMPANY,
        )
        session.add_all([owner, other, company_acme_user, company_beta_user])
        session.flush()
        user_ids.extend(
            (owner.id, other.id, company_acme_user.id, company_beta_user.id)
        )

        session.add_all(
            [
                Candidate(
                    id=owner.id,
                    full_name="Applications Owner",
                    cpf="11144477735",
                    birth_date=date(1970, 1, 1),
                    phone="+5551999990000",
                ),
                Candidate(
                    id=other.id,
                    full_name="Applications Other",
                    cpf="22255588846",
                    birth_date=date(1971, 1, 1),
                    phone="+5551999990001",
                ),
                Company(
                    id=company_acme_user.id,
                    cnpj="20000000000100",
                    legal_name="Acme Synthetic Services Ltd.",
                    trade_name="Acme Synthetic Services",
                    corporate_email=company_acme_user.email,
                    status="approved",
                ),
                Company(
                    id=company_beta_user.id,
                    cnpj="20000000000200",
                    legal_name="Beta Synthetic Works Ltd.",
                    trade_name="Beta Synthetic Works",
                    corporate_email=company_beta_user.email,
                    status="approved",
                ),
            ]
        )

        skill_python = Skill(name="Applications Python", type="hard")
        skill_english = Skill(name="Applications English", type="soft")
        skill_spanish = Skill(name="Applications Spanish", type="soft")
        session.add_all([skill_python, skill_english, skill_spanish])
        session.flush()
        skill_ids.extend((skill_python.id, skill_english.id, skill_spanish.id))

        far_future = date(2099, 12, 31)

        def make_job(*, company_id: UUID, status: JobStatus, title: str) -> Job:
            return Job(
                company_id=company_id,
                title=title,
                description="Synthetic job for applications tests.",
                work_mode="remote",
                status=status,
                closing_date=far_future,
            )

        job_target = make_job(
            company_id=company_acme_user.id,
            status=JobStatus.PUBLISHED,
            title="Applications Target Role",
        )
        job_similar_strong = make_job(
            company_id=company_acme_user.id,
            status=JobStatus.PUBLISHED,
            title="Applications Similar Strong Role",
        )
        job_similar_weak = make_job(
            company_id=company_beta_user.id,
            status=JobStatus.PUBLISHED,
            title="Applications Similar Weak Role",
        )
        job_no_match = make_job(
            company_id=company_beta_user.id,
            status=JobStatus.PUBLISHED,
            title="Applications No Match Role",
        )
        job_already_applied = make_job(
            company_id=company_acme_user.id,
            status=JobStatus.PUBLISHED,
            title="Applications Already Applied Role",
        )
        job_draft = make_job(
            company_id=company_acme_user.id,
            status=JobStatus.DRAFT,
            title="Applications Draft Role",
        )
        job_active = make_job(
            company_id=company_beta_user.id,
            status=JobStatus.PUBLISHED,
            title="Applications Active Role",
        )
        job_withdrawn = make_job(
            company_id=company_acme_user.id,
            status=JobStatus.PUBLISHED,
            title="Applications Withdrawn Role",
        )
        session.add_all(
            [
                job_target,
                job_similar_strong,
                job_similar_weak,
                job_no_match,
                job_already_applied,
                job_draft,
                job_active,
                job_withdrawn,
            ]
        )
        session.flush()

        session.add_all(
            [
                JobSkill(job_id=job_target.id, skill_id=skill_python.id),
                JobSkill(job_id=job_target.id, skill_id=skill_english.id),
                JobSkill(job_id=job_similar_strong.id, skill_id=skill_python.id),
                JobSkill(job_id=job_similar_strong.id, skill_id=skill_english.id),
                JobSkill(job_id=job_similar_weak.id, skill_id=skill_python.id),
                JobSkill(job_id=job_no_match.id, skill_id=skill_spanish.id),
                JobSkill(job_id=job_already_applied.id, skill_id=skill_python.id),
                JobSkill(job_id=job_already_applied.id, skill_id=skill_english.id),
                JobSkill(job_id=job_draft.id, skill_id=skill_python.id),
                JobSkill(job_id=job_draft.id, skill_id=skill_english.id),
            ]
        )

        application_not_selected = Application(
            candidate_id=owner.id,
            job_id=job_target.id,
            status=ApplicationStatus.NOT_SELECTED,
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
            closed_at=now - timedelta(days=3),
        )
        application_active = Application(
            candidate_id=owner.id,
            job_id=job_active.id,
            status=ApplicationStatus.APPLIED,
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=5),
        )
        application_withdrawn = Application(
            candidate_id=owner.id,
            job_id=job_withdrawn.id,
            status=ApplicationStatus.WITHDRAWN,
            created_at=now - timedelta(days=8),
            updated_at=now - timedelta(days=8),
            closed_at=now - timedelta(days=1),
        )
        application_on_already_applied_job = Application(
            candidate_id=owner.id,
            job_id=job_already_applied.id,
            status=ApplicationStatus.APPLIED,
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
        )
        application_other_candidate = Application(
            candidate_id=other.id,
            job_id=job_target.id,
            status=ApplicationStatus.APPLIED,
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
        session.add_all(
            [
                application_not_selected,
                application_active,
                application_withdrawn,
                application_on_already_applied_job,
                application_other_candidate,
            ]
        )
        session.flush()

        result = ApplicationsScenario(
            now=now,
            owner_id=owner.id,
            other_id=other.id,
            company_acme_id=company_acme_user.id,
            company_beta_id=company_beta_user.id,
            job_target_id=job_target.id,
            job_similar_strong_id=job_similar_strong.id,
            job_similar_weak_id=job_similar_weak.id,
            job_no_match_id=job_no_match.id,
            job_already_applied_id=job_already_applied.id,
            job_draft_id=job_draft.id,
            job_active_id=job_active.id,
            job_withdrawn_id=job_withdrawn.id,
            application_not_selected_id=application_not_selected.id,
            application_active_id=application_active.id,
            application_withdrawn_id=application_withdrawn.id,
            application_on_already_applied_job_id=(
                application_on_already_applied_job.id
            ),
            application_other_candidate_id=application_other_candidate.id,
        )

    yield result

    with factory.begin() as session:
        session.execute(delete(AppUser).where(AppUser.id.in_(user_ids)))
        session.execute(delete(Skill).where(Skill.id.in_(skill_ids)))
