from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.passwords import hash_password
from app.db.models import (
    Address,
    Administrator,
    Application,
    AppUser,
    AttachedCertificate,
    Candidate,
    Certification,
    Company,
    Education,
    Event,
    Experience,
    Job,
    Language,
    Notification,
    Resume,
    Skill,
    Training,
)
from app.db.session import get_session_factory

DEMO_PASSWORD = "LocalDemoOnly!2026"
SEED_NAMESPACE = uuid5(NAMESPACE_URL, "https://seniors.example.invalid/seed/v1")


def seed_id(name: str) -> UUID:
    return uuid5(SEED_NAMESPACE, name)


def add_if_missing(session: Session, model: type[object], **values: object) -> None:
    session.execute(insert(model).values(**values).on_conflict_do_nothing())


def seed_database(session: Session) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    password_hash = hash_password(DEMO_PASSWORD)
    candidate_id = seed_id("user-candidate")
    company_id = seed_id("user-company")
    administrator_id = seed_id("user-administrator")
    address_id = seed_id("address-company")
    skill_id = seed_id("skill-python")
    resume_id = seed_id("resume-candidate")
    job_id = seed_id("job-company")

    add_if_missing(
        session,
        Address,
        id=address_id,
        street="Example Avenue",
        number="100",
        complement="Suite A",
        neighborhood="Example District",
        city="Porto Alegre",
        state="RS",
        zip_code="90000000",
        code="LOCAL-001",
        created_at=now,
    )
    add_if_missing(
        session,
        Skill,
        id=skill_id,
        name="Python",
        type="hard",
        created_at=now,
    )
    for user_id, email, user_type in (
        (candidate_id, "candidate@example.invalid", "candidate"),
        (company_id, "representative@company.example.invalid", "company"),
        (administrator_id, "administrator@example.invalid", "administrator"),
    ):
        add_if_missing(
            session,
            AppUser,
            id=user_id,
            email=email,
            password_hash=password_hash,
            user_type=user_type,
            account_status="active",
            created_at=now,
            updated_at=now,
        )
    add_if_missing(
        session,
        Candidate,
        id=candidate_id,
        full_name="Demo Candidate",
        cpf="00000000000",
        birth_date=date(1960, 1, 1),
        age=66,
        phone="+5500000000000",
        city="Porto Alegre",
        state="RS",
        availability="available",
        accepts_automatic_application=True,
        terms_version_accepted="local-v1",
        terms_accepted_at=now,
    )
    add_if_missing(
        session,
        Resume,
        id=resume_id,
        candidate_id=candidate_id,
        summary="Synthetic local profile.",
        employment_status="unemployed",
        employment_status_since=date(2025, 1, 1),
        desired_salary=Decimal("5000.00"),
        availability_start_date=date(2026, 1, 1),
        completion_percentage=100,
        skill_ids=[skill_id],
        created_at=now,
        updated_at=now,
    )
    add_if_missing(
        session,
        Experience,
        id=seed_id("experience-candidate"),
        resume_id=resume_id,
        company_name="Example Organization",
        role="Software Specialist",
        start_date=date(2010, 1, 1),
        end_date=date(2024, 12, 31),
        description="Synthetic local experience.",
    )
    add_if_missing(
        session,
        Education,
        id=seed_id("education-candidate"),
        resume_id=resume_id,
        institution="Example Institute",
        degree="Bachelor",
        field="Technology",
        start_date=date(2000, 1, 1),
        end_date=date(2004, 12, 31),
    )
    add_if_missing(
        session,
        Certification,
        id=seed_id("certification-candidate"),
        resume_id=resume_id,
        name="Example Certificate",
        issuer="Example Institute",
        issued_date=date(2025, 1, 1),
    )
    add_if_missing(
        session,
        Language,
        id=seed_id("language-candidate"),
        resume_id=resume_id,
        name="Portuguese",
        proficiency="native",
    )
    add_if_missing(
        session,
        AttachedCertificate,
        id=seed_id("attached-certificate-candidate"),
        resume_id=resume_id,
        file_url="https://files.example.invalid/certificate.pdf",
        uploaded_at=now,
    )
    add_if_missing(
        session,
        Company,
        id=company_id,
        cnpj="00000000000000",
        legal_name="Example Company Ltd.",
        trade_name="Example Company",
        primary_cnae="6201501",
        corporate_email="representative@company.example.invalid",
        corporate_email_confirmed=True,
        company_size="small",
        industry="Technology",
        linkedin_url="https://company.example.invalid/linkedin",
        linkedin_verified=False,
        address_id=address_id,
        status="approved",
        terms_version_accepted="local-v1",
        terms_accepted_at=now,
    )
    add_if_missing(
        session,
        Administrator,
        id=administrator_id,
        full_name="Demo Administrator",
        active=True,
    )
    add_if_missing(
        session,
        Job,
        id=job_id,
        company_id=company_id,
        title="Example Software Role",
        description="Synthetic local job.",
        work_mode="remote",
        location="Brazil",
        contract_type="full_time",
        salary_max=Decimal("8000.00"),
        status="published",
        published_at=now,
        closing_date=date(2027, 1, 1),
        featured=False,
        desired_skills=[{"skill_id": str(skill_id), "required": True}],
        created_at=now,
        updated_at=now,
    )
    add_if_missing(
        session,
        Application,
        id=seed_id("application-candidate-job"),
        candidate_id=candidate_id,
        job_id=job_id,
        type="active",
        status="applied",
        match_score=90,
        created_at=now,
        updated_at=now,
    )
    add_if_missing(
        session,
        Training,
        id=seed_id("training-local"),
        title="Example Digital Skills Training",
        provider="Example Institute",
        area="Technology",
        training_mode="online",
        workload_hours=20,
        free=True,
        external_link="https://training.example.invalid/course",
        published=True,
        created_at=now,
        updated_at=now,
    )
    add_if_missing(
        session,
        Event,
        id=seed_id("event-local"),
        user_id=candidate_id,
        event_type="local_seed_created",
        details={"source": "local_seed"},
        created_at=now,
    )
    add_if_missing(
        session,
        Notification,
        id=seed_id("notification-local"),
        user_id=candidate_id,
        type="local_welcome",
        message="Welcome to the local demo environment.",
        read=False,
        details={"source": "local_seed"},
        created_at=now,
    )


def main() -> None:
    settings = get_settings()
    if settings.app_env not in {"local", "test"}:
        raise RuntimeError("Seed is allowed only in local and test environments")

    with get_session_factory().begin() as session:
        seed_database(session)


if __name__ == "__main__":
    main()
