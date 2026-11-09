from app.db.models import TrainingJob
from tests.db.models.assertions import foreign_key_for, has_unique_constraint


def test_training_and_job_foreign_keys_cascade() -> None:
    for column_name in ("training_id", "job_id"):
        foreign_key = foreign_key_for(TrainingJob, column_name)

        assert foreign_key.ondelete == "CASCADE"
        assert foreign_key.deferrable is True


def test_a_job_is_linked_to_a_training_only_once() -> None:
    assert has_unique_constraint(TrainingJob, ["training_id", "job_id"])
