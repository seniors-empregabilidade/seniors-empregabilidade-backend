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
        "email_verification_request",
        "event",
        "experience",
        "job",
        "language",
        "notification",
        "resume",
        "skill",
        "training",
    }
