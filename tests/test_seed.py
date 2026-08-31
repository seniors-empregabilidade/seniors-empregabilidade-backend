from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from scripts import seed


def test_seed_rejects_non_local_environments(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory = MagicMock()
    monkeypatch.setattr(seed, "get_settings", lambda: Settings(app_env="production"))
    monkeypatch.setattr(seed, "get_session_factory", session_factory)

    with pytest.raises(RuntimeError, match="only in local and test"):
        seed.main()

    session_factory.assert_not_called()


def test_seed_ids_are_deterministic() -> None:
    assert seed.seed_id("candidate") == seed.seed_id("candidate")
    assert seed.seed_id("candidate") != seed.seed_id("company")
