import pytest

from app.candidates.domain.resume_completeness import missing_resume_fields


def test_all_missing_fields_follow_the_frontend_contract_order() -> None:
    assert missing_resume_fields(
        city=None,
        state=None,
        summary=None,
        has_experience=False,
        has_education=False,
        has_skill=False,
    ) == ("city", "state", "summary", "experiences", "education", "skills")


def test_a_complete_resume_has_no_missing_fields() -> None:
    assert (
        missing_resume_fields(
            city="Porto Alegre",
            state="RS",
            summary="Experienced professional",
            has_experience=True,
            has_education=True,
            has_skill=True,
        )
        == ()
    )


@pytest.mark.parametrize("field", ["city", "state", "summary"])
def test_blank_text_counts_as_missing(field: str) -> None:
    values: dict[str, str | None] = {
        "city": "Porto Alegre",
        "state": "RS",
        "summary": "Experienced professional",
    }
    values[field] = "  "

    assert missing_resume_fields(
        city=values["city"],
        state=values["state"],
        summary=values["summary"],
        has_experience=True,
        has_education=True,
        has_skill=True,
    ) == (field,)


@pytest.mark.parametrize(
    ("field", "flags"),
    [
        ("experiences", (False, True, True)),
        ("education", (True, False, True)),
        ("skills", (True, True, False)),
    ],
)
def test_each_collection_is_required(
    field: str, flags: tuple[bool, bool, bool]
) -> None:
    assert missing_resume_fields(
        city="Porto Alegre",
        state="RS",
        summary="Experienced professional",
        has_experience=flags[0],
        has_education=flags[1],
        has_skill=flags[2],
    ) == (field,)
