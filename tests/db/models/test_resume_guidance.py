from app.db.models import ResumeGuidance
from tests.db.models.assertions import foreign_key_for, has_check_constraint, table_for


def test_guidance_has_length_and_candidate_lookup_constraints() -> None:
    table = table_for(ResumeGuidance)

    assert has_check_constraint(ResumeGuidance, "ck_resume_guidance_note_length")
    index = next(
        index
        for index in table.indexes
        if index.name == "ix_resume_guidance_candidate_id_created_at_id"
    )
    assert [str(expression) for expression in index.expressions] == [
        "resume_guidance.candidate_id",
        "resume_guidance.created_at DESC",
        "resume_guidance.id DESC",
    ]
    assert table.c.candidate_id.nullable is False
    assert table.c.administrator_id.nullable is False
    assert foreign_key_for(ResumeGuidance, "candidate_id").ondelete == "CASCADE"
    assert foreign_key_for(ResumeGuidance, "administrator_id").ondelete == "RESTRICT"
