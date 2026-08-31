from typing import cast

from sqlalchemy import CheckConstraint, Enum, ForeignKeyConstraint, Index, Table

from app.db.models import Company


def test_status_uses_a_postgresql_enum() -> None:
    assert isinstance(Company.__table__.c.status.type, Enum)


def test_cnpj_format_constraint_is_declared() -> None:
    company_table = cast(Table, Company.__table__)

    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_company_cnpj_format"
        for constraint in company_table.constraints
    )


def test_address_foreign_key_sets_null_and_is_deferrable() -> None:
    company_table = cast(Table, Company.__table__)
    address_fk = next(
        constraint
        for constraint in company_table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.column_keys == ["address_id"]
    )

    assert address_fk.ondelete == "SET NULL"
    assert address_fk.deferrable is True
    assert address_fk.initially == "IMMEDIATE"


def test_status_index_is_declared() -> None:
    company_table = cast(Table, Company.__table__)

    assert any(
        isinstance(index, Index) and index.name == "ix_company_status"
        for index in company_table.indexes
    )
