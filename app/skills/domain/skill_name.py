import unicodedata
from dataclasses import dataclass

MAX_SKILL_NAME_LENGTH = 100


class InvalidSkillNameError(ValueError):
    """The supplied value cannot represent a skill name."""


@dataclass(frozen=True, slots=True)
class SkillName:
    """A catalog skill name and the form used to compare it with another one.

    Two names are the same skill when they differ only by surrounding or repeated
    spaces, letter case, or accents, so that "Gestão de equipes" typed by a company
    matches "gestao de equipes" already stored in the catalog.
    """

    value: str
    normalized: str

    @classmethod
    def parse(cls, raw_value: str) -> SkillName:
        value = " ".join(raw_value.split())
        if not value or len(value) > MAX_SKILL_NAME_LENGTH:
            raise InvalidSkillNameError

        return cls(value, _without_case_or_accents(value))


def _without_case_or_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
