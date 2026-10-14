from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.storage.document_storage import DocumentStorage
from app.storage.integrations.s3 import S3DocumentStorage


@lru_cache
def _configured_storage(
    bucket: str,
    region: str,
    endpoint_url: str | None,
    access_key_id: str | None,
    secret_access_key: str | None,
) -> DocumentStorage:
    return S3DocumentStorage(
        bucket=bucket,
        region=region,
        endpoint_url=endpoint_url,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
    )


def get_document_storage(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentStorage:
    secret = settings.s3_secret_access_key
    endpoint = settings.s3_endpoint_url
    return _configured_storage(
        settings.uploads_bucket,
        settings.uploads_region,
        str(endpoint).rstrip("/") if endpoint else None,
        settings.s3_access_key_id,
        secret.get_secret_value() if secret else None,
    )
