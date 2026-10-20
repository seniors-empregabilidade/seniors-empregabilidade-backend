from app.storage.exceptions import DocumentStorageUnavailableError


class FakeDocumentStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.unavailable = False
        self.calls: list[str] = []

    def _call(self, operation: str) -> None:
        self.calls.append(operation)
        if self.unavailable:
            raise DocumentStorageUnavailableError

    def put(self, key: str, content: bytes, *, content_type: str) -> None:
        self._call("put")
        self.objects[key] = (content, content_type)

    def delete(self, key: str) -> None:
        self._call("delete")
        self.objects.pop(key, None)

    def download_url(
        self, key: str, *, filename: str, content_type: str, expires_in: int
    ) -> str:
        self._call("download_url")
        return f"https://storage.example.invalid/{key}?expires_in={expires_in}"
