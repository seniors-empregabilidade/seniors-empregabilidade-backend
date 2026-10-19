import logging

from app.storage.document_storage import DocumentStorage
from app.storage.exceptions import DocumentStorageUnavailableError

_logger = logging.getLogger("app.storage")


def remove_quietly(storage: DocumentStorage, key: str) -> None:
    """Delete an object whose row is already gone; a failure leaves an orphan."""
    try:
        storage.delete(key)
    except DocumentStorageUnavailableError:
        _logger.warning("document_cleanup_failed")
