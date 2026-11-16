from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.db import models as models
from app.db.base import Base

assert models

config = context.config

if config.config_file_name is not None:
    import logging

    # Preserve the existing logging configuration so that fileConfig does not
    # reset the root logger level or remove handlers installed by the app or
    # by test harnesses (e.g. pytest's caplog LogCaptureHandler).
    _root = logging.getLogger()
    _saved_level = _root.level
    _saved_handlers = list(_root.handlers)
    fileConfig(config.config_file_name, disable_existing_loggers=False)
    _root.handlers = _saved_handlers
    _root.setLevel(_saved_level)

config.set_main_option(
    "sqlalchemy.url",
    get_settings().database_url.replace("%", "%%"),
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
