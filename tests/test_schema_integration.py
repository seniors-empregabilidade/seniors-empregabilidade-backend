import os
from typing import cast

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.dialects.postgresql.base import PGInspector

from app.db.models import AppUser
from app.db.session import get_engine, get_session_factory
from scripts.seed import seed_database

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
    reason="requires RUN_DATABASE_INTEGRATION_TESTS=1 and migrated PostgreSQL",
)


@pytest.mark.integration
def test_migrated_schema_contains_postgresql_domain_objects() -> None:
    inspector = inspect(get_engine())
    pg_inspector = cast(PGInspector, inspector)

    assert set(inspector.get_table_names()) >= {
        "address",
        "app_user",
        "candidate",
        "company",
        "job",
        "job_skill",
        "resume",
        "resume_skill",
    }
    assert len(pg_inspector.get_enums()) == 12
    assert any(
        check["name"] == "ck_company_cnpj_format"
        for check in inspector.get_check_constraints("company")
    )
    for join_table in ("job_skill", "resume_skill"):
        assert any(
            foreign_key["referred_table"] == "skill"
            for foreign_key in inspector.get_foreign_keys(join_table)
        )


@pytest.mark.integration
def test_seed_is_idempotent_and_cannot_authenticate() -> None:
    factory = get_session_factory()
    with factory.begin() as session:
        seed_database(session)
    with factory.begin() as session:
        seed_database(session)
    with factory() as session:
        users = session.scalars(select(AppUser)).all()

    assert len(users) == 3
    assert all(user.identity_subject is None for user in users)
    assert "password_hash" not in AppUser.__table__.columns
