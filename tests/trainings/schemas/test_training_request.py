from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.models.enums import TrainingMode
from app.trainings.schemas import TrainingRequest, TrainingUpdateRequest

VALID = {
    "title": "  Excel basico  ",
    "institution": "Escola Sintetica",
    "mode": "online",
    "external_link": "https://cursos.example.invalid/excel",
}


def test_text_is_stripped_and_defaults_keep_the_course_hidden() -> None:
    request = TrainingRequest.model_validate(VALID)

    assert request.title == "Excel basico"
    assert request.mode is TrainingMode.ONLINE
    assert request.published is False
    assert request.skill_ids == []
    assert request.job_ids == []


def test_repeated_relation_ids_are_collapsed_in_order() -> None:
    first, second = uuid4(), uuid4()

    request = TrainingRequest.model_validate(
        {**VALID, "skill_ids": [first, second, first]}
    )

    assert request.skill_ids == [first, second]


@pytest.mark.parametrize(
    "link",
    [
        "ftp://cursos.example.invalid/a",
        "javascript:alert(1)",
        "cursos.example.invalid",
        "https://",
        "https://cursos.example.invalid/a b",
        "https://cursos.example.invalid/" + "a" * 2048,
    ],
)
def test_external_link_must_be_a_web_url(link: str) -> None:
    with pytest.raises(ValidationError):
        TrainingRequest.model_validate({**VALID, "external_link": link})


@pytest.mark.parametrize(
    "change",
    [
        {"title": "   "},
        {"title": "x" * 151},
        {"institution": ""},
        {"mode": "carrier-pigeon"},
        {"skill_ids": [str(uuid4())] * 1 + ["not-a-uuid"]},
        {"job_ids": [str(uuid4()) for _ in range(51)]},
        {"unknown": 1},
    ],
)
def test_invalid_fields_are_rejected(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TrainingRequest.model_validate({**VALID, **change})


@pytest.mark.parametrize("missing", ["title", "institution", "mode", "external_link"])
def test_required_fields_are_enforced(missing: str) -> None:
    payload = {key: value for key, value in VALID.items() if key != missing}

    with pytest.raises(ValidationError):
        TrainingRequest.model_validate(payload)


def test_an_update_needs_at_least_one_field() -> None:
    with pytest.raises(ValidationError):
        TrainingUpdateRequest.model_validate({})


@pytest.mark.parametrize("field", ["title", "published", "skill_ids", "job_ids"])
def test_an_update_cannot_null_a_field(field: str) -> None:
    with pytest.raises(ValidationError):
        TrainingUpdateRequest.model_validate({field: None})


def test_an_update_may_clear_the_relations_with_an_empty_list() -> None:
    request = TrainingUpdateRequest.model_validate({"skill_ids": []})

    assert request.skill_ids == []
    assert request.job_ids is None
