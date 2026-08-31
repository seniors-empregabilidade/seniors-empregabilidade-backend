from app.db.models import Education
from tests.db.models.assertions import foreign_key_for, has_index


def test_resume_foreign_key_cascades_and_is_indexed() -> None:
    resume_fk = foreign_key_for(Education, "resume_id")

    assert resume_fk.ondelete == "CASCADE"
    assert resume_fk.deferrable is True
    assert has_index(Education, "ix_education_resume_id")
