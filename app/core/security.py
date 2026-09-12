from passlib.context import CryptContext  # type: ignore[import-untyped]

# Configure bcrypt hashing algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the provided plain-text password."""
    from typing import cast

    return cast(str, pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that a plain-text password matches a stored bcrypt hash."""
    from typing import cast

    return cast(bool, pwd_context.verify(plain_password, hashed_password))
