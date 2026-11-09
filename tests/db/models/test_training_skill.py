from app.db.models import TrainingSkill
from tests.db.models.assertions import foreign_key_for, has_unique_constraint


def test_training_and_skill_foreign_keys_cascade() -> None:
    for column_name in ("training_id", "skill_id"):
        foreign_key = foreign_key_for(TrainingSkill, column_name)

        assert foreign_key.ondelete == "CASCADE"
        assert foreign_key.deferrable is True


def test_a_skill_is_linked_to_a_training_only_once() -> None:
    assert has_unique_constraint(TrainingSkill, ["training_id", "skill_id"])
