from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AfterValidator, Field, StringConstraints

MAX_TITLE_LENGTH = 150
MAX_INSTITUTION_LENGTH = 150
MAX_EXTERNAL_LINK_LENGTH = 2048
MAX_RELATED_RECORDS = 50


def _web_link(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("external link must be an http or https URL")
    if any(character.isspace() or ord(character) < 32 for character in value):
        raise ValueError("external link must not contain whitespace")
    return value


def _without_repeats(values: list[UUID]) -> list[UUID]:
    return list(dict.fromkeys(values))


TrainingTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TITLE_LENGTH),
]
TrainingInstitution = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MAX_INSTITUTION_LENGTH
    ),
]
ExternalLink = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MAX_EXTERNAL_LINK_LENGTH
    ),
    AfterValidator(_web_link),
]
RelatedIds = Annotated[
    list[UUID],
    Field(max_length=MAX_RELATED_RECORDS),
    AfterValidator(_without_repeats),
]
