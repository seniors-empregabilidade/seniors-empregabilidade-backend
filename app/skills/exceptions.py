from app.core.errors import ProblemException


class CatalogSkillNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="skill_not_found",
            detail="The skill was not found.",
        )


class SkillNameConflictError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="skill_name_conflict",
            detail="Another catalog skill already has this name.",
            errors={"name": ["Another catalog skill already has this name."]},
        )
