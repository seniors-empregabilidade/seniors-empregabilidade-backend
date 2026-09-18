from app.db.base import Base


def test_metadata_contains_the_confirmed_domain_schema() -> None:
    assert set(Base.metadata.tables) == {
        "address",
        "administrator",
        "app_user",
        "application",
        "attached_certificate",
        "candidate",
        "certification",
        "company",
        "education",
        "event",
        "experience",
        "job",
        "job_skill",
        "language",
        "notification",
        "resume",
        "resume_skill",
        "skill",
        "training",
    }
