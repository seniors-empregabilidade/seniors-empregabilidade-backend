from app.db.models import AttachedCertificate
from tests.db.models.assertions import foreign_key_for, has_index


def test_resume_foreign_key_cascades_and_is_indexed() -> None:
    resume_fk = foreign_key_for(AttachedCertificate, "resume_id")

    assert resume_fk.ondelete == "CASCADE"
    assert resume_fk.deferrable is True
    assert has_index(AttachedCertificate, "ix_attached_certificate_resume_id")


def test_uploaded_at_has_a_database_default() -> None:
    assert (
        str(AttachedCertificate.__table__.c.uploaded_at.server_default.arg) == "now()"
    )
