from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.identity.integrations.cognito import CognitoIdentityProvider
from app.identity.provider import IdentityProvider


@lru_cache
def _configured_provider(
    region: str, pool_id: str, client_id: str, client_secret: str | None
) -> IdentityProvider:
    return CognitoIdentityProvider(
        region=region, pool_id=pool_id, client_id=client_id, client_secret=client_secret
    )


def get_identity_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> IdentityProvider:
    secret = settings.cognito_client_secret
    return _configured_provider(
        settings.cognito_region,
        settings.cognito_user_pool_id,
        settings.cognito_client_id,
        secret.get_secret_value() if secret else None,
    )
