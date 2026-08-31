import os
from typing import cast

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.dialects.postgresql.base import PGInspector

from app.core.passwords import verify_password
from app.db.models import AppUser
from app.db.session import get_engine, get_session_factory
from scripts.seed import DEMO_PASSWORD, seed_database

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
        "resume",
    }
    assert len(pg_inspector.get_enums()) == 12
    assert any(
        check["name"] == "ck_company_cnpj_format"
        for check in inspector.get_check_constraints("company")
    )


@pytest.mark.integration
def test_seed_is_idempotent_and_uses_argon2id() -> None:
    factory = get_session_factory()
    with factory.begin() as session:
        seed_database(session)
    with factory.begin() as session:
        seed_database(session)
    with factory() as session:
        users = session.scalars(select(AppUser)).all()

    assert len(users) == 3
    assert all(user.password_hash.startswith("$argon2id$") for user in users)
    assert all(verify_password(user.password_hash, DEMO_PASSWORD) for user in users)
