from app.core.passwords import hash_password, verify_password


def test_passwords_use_argon2id_and_can_be_verified() -> None:
    password_hash = hash_password("test-password")

    assert password_hash.startswith("$argon2id$")
    assert verify_password(password_hash, "test-password") is True
    assert verify_password(password_hash, "wrong-password") is False


def test_invalid_hash_fails_verification_safely() -> None:
    assert verify_password("not-a-password-hash", "test-password") is False
