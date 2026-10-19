from typing import Protocol


class DocumentStorage(Protocol):
    def put(self, key: str, content: bytes, *, content_type: str) -> None: ...

    def delete(self, key: str) -> None: ...

    def download_url(
        self, key: str, *, filename: str, content_type: str, expires_in: int
    ) -> str:
        """Return a short-lived URL that downloads the object as an attachment."""
        ...
