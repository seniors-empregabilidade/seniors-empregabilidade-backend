class JobWithoutRequiredSkillsError(ValueError):
    """A compatibility score needs at least one required skill to compare against."""

    def __init__(self) -> None:
        super().__init__("a job must require at least one skill")
