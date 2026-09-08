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


def test_seed_addresses_default_to_synthetic_values() -> None:
    users = seed.parse_users([])

    assert users == seed.DEMO_USERS
    assert all(email.endswith(".invalid") for _name, email, _type in users)


def test_seed_addresses_can_be_replaced_without_editing_the_repository() -> None:
    users = seed.parse_users(["--candidate-email", "person@example.invalid"])

    by_name = {name: email for name, email, _type in users}
    assert by_name["user-candidate"] == "person@example.invalid"
    # The other two keep their defaults, and the roles are never overridable.
    assert by_name["user-company"] == "representative@company.example.invalid"
    assert [user_type for _name, _email, user_type in users] == [
        "candidate",
        "company",
        "administrator",
    ]


def test_seed_ids_do_not_depend_on_the_address() -> None:
    replaced = seed.parse_users(["--candidate-email", "person@example.invalid"])

    # A moved address must land on the same row, never create a second account.
    assert replaced[0][0] == seed.DEMO_USERS[0][0]
    assert seed.seed_id(replaced[0][0]) == seed.seed_id(seed.DEMO_USERS[0][0])
