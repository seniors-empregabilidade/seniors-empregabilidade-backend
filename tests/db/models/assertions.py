from typing import cast

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase


def table_for(model: type[DeclarativeBase]) -> Table:
    return cast(Table, model.__table__)


def foreign_key_for(
    model: type[DeclarativeBase], column_name: str
) -> ForeignKeyConstraint:
    table = table_for(model)
    return next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.column_keys == [column_name]
    )


def has_index(model: type[DeclarativeBase], name: str) -> bool:
    return any(index.name == name for index in table_for(model).indexes)


def has_unique_constraint(
    model: type[DeclarativeBase], column_names: list[str]
) -> bool:
    return any(
        isinstance(constraint, UniqueConstraint)
        and list(constraint.columns.keys()) == column_names
        for constraint in table_for(model).constraints
    )


def has_check_constraint(model: type[DeclarativeBase], name: str) -> bool:
    return any(
        isinstance(constraint, CheckConstraint) and constraint.name == name
        for constraint in table_for(model).constraints
    )
