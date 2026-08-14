from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.db import session


def test_database_readiness_executes_a_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = 1
    monkeypatch.setattr(session, "get_engine", lambda: engine)

    assert session.is_database_ready() is True


def test_database_readiness_handles_connection_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock()
    engine.connect.side_effect = SQLAlchemyError("connection unavailable")
    monkeypatch.setattr(session, "get_engine", lambda: engine)

    assert session.is_database_ready() is False
