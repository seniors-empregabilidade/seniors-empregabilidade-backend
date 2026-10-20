import logging

import pytest

from app.storage.removal import remove_quietly
from tests.storage.fakes import FakeDocumentStorage


def test_removes_the_object() -> None:
    storage = FakeDocumentStorage()
    storage.objects["key"] = (b"%PDF-", "application/pdf")

    remove_quietly(storage, "key")

    assert storage.objects == {}


def test_unavailable_storage_is_logged_without_raising(
    caplog: pytest.LogCaptureFixture,
) -> None:
    storage = FakeDocumentStorage()
    storage.unavailable = True

    with caplog.at_level(logging.WARNING, logger="app.storage"):
        remove_quietly(storage, "certifications/abc/def")

    assert [record.getMessage() for record in caplog.records] == [
        "document_cleanup_failed"
    ]
    assert "certifications" not in caplog.text
