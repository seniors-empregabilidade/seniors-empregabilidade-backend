import pytest

from tests.identity.fakes import FakeIdentityProvider


@pytest.fixture
def identity_provider() -> FakeIdentityProvider:
    return FakeIdentityProvider()
