import unicodedata
from dataclasses import dataclass

MAX_SKILL_NAME_LENGTH = 100

# Unicode categories dropped before two names are compared: nonspacing marks are
# the accents themselves, modifier symbols are accents typed on their own
# (a lone acute accent), and format characters are invisible (a zero-width space).
_IGNORED_CATEGORIES = frozenset({"Mn", "Sk", "Cf"})


class InvalidSkillNameError(ValueError):
    """The supplied value cannot represent a skill name."""


@dataclass(frozen=True, slots=True)
class SkillName:
    """A catalog skill name and the form used to compare it with another one.

    Two names are the same skill when they differ only by surrounding or repeated
    spaces, letter case, accents or invisible characters, so that "Gestão de
    equipes" typed by a company matches "gestao de equipes" already stored in the
    catalog.
    """

    value: str
    normalized: str

    @classmethod
    def parse(cls, raw_value: str) -> SkillName:
        value = " ".join(raw_value.split())
        # PostgreSQL cannot store NUL, and no other control character belongs in a
        # name someone reads.
        if len(value) > MAX_SKILL_NAME_LENGTH or _has_control_character(value):
            raise InvalidSkillNameError

        normalized = normalize_skill_name(value)
        # Folding can lengthen a name ("ß" becomes "ss"), and a name made only of
        # accents or invisible characters has nothing left to compare.
        if not normalized or len(normalized) > MAX_SKILL_NAME_LENGTH:
            raise InvalidSkillNameError

        return cls(value, normalized)


def normalize_skill_name(raw_value: str) -> str:
    """Return the form in which two skill names are compared."""
    decomposed = unicodedata.normalize("NFKD", raw_value.casefold())
    kept = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) not in _IGNORED_CATEGORIES
    )
    return " ".join(kept.split())


def _has_control_character(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)
