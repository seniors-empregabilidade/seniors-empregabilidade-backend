from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.storage.exceptions import DocumentStorageUnavailableError


class S3DocumentStorage:
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path" if endpoint_url else "virtual"},
                connect_timeout=3,
                read_timeout=10,
                retries={"total_max_attempts": 2},
            ),
        )

    def put(self, key: str, content: bytes, *, content_type: str) -> None:
        self._require_bucket()
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise DocumentStorageUnavailableError from exc

    def delete(self, key: str) -> None:
        self._require_bucket()
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise DocumentStorageUnavailableError from exc

    def download_url(
        self, key: str, *, filename: str, content_type: str, expires_in: int
    ) -> str:
        self._require_bucket()
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    "ResponseContentType": content_type,
                    "ResponseContentDisposition": attachment(filename),
                },
                ExpiresIn=expires_in,
            )
        except (BotoCoreError, ClientError) as exc:
            raise DocumentStorageUnavailableError from exc

    def _require_bucket(self) -> None:
        # Checked per call so certification CRUD works where no bucket is set.
        if not self._bucket:
            raise DocumentStorageUnavailableError


def attachment(filename: str) -> str:
    fallback = filename.encode("ascii", "ignore").decode().replace('"', "") or "file"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"
