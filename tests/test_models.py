from typing import cast

from sqlalchemy import CheckConstraint, Enum, ForeignKeyConstraint, Index, String, Table
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.sqltypes import ARRAY

from app.db.base import Base
from app.db.models import Address, Company, Job, Resume


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
        "language",
        "notification",
        "resume",
        "skill",
        "training",
    }
    neighborhood_type = cast(String, Address.__table__.c.neighborhood.type)
    assert neighborhood_type.length == 100


def test_postgresql_specific_types_and_defaults_are_preserved() -> None:
    assert isinstance(Resume.__table__.c.skill_ids.type, ARRAY)
    assert isinstance(Job.__table__.c.desired_skills.type, JSONB)
    assert isinstance(Company.__table__.c.status.type, Enum)
    assert str(Resume.__table__.c.skill_ids.server_default.arg) == "'{}'::uuid[]"


def test_constraints_indexes_and_foreign_keys_are_declared() -> None:
    company_table = cast(Table, Company.__table__)
    company_constraints = company_table.constraints
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_company_cnpj_format"
        for constraint in company_constraints
    )
    address_fk = next(
        constraint
        for constraint in company_constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.column_keys == ["address_id"]
    )
    assert address_fk.ondelete == "SET NULL"
    assert address_fk.deferrable is True
    assert address_fk.initially == "IMMEDIATE"
    assert any(
        isinstance(index, Index) and index.name == "ix_company_status"
        for index in company_table.indexes
    )
