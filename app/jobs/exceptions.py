from app.core.errors import ProblemException


class UnknownSkillsError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="unknown_skills",
            detail="One or more skills were not found.",
            errors={"skill_ids": ["One or more skills were not found."]},
        )


class ClosingDateInThePastError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="closing_date_in_the_past",
            detail="The closing date cannot be in the past.",
            errors={"closing_date": ["The closing date cannot be in the past."]},
        )
