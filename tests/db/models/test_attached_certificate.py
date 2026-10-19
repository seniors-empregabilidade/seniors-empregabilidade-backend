from app.db.models import AttachedCertificate
from tests.db.models.assertions import foreign_key_for, has_unique_constraint


def test_certification_foreign_key_cascades_and_is_unique() -> None:
    certification_fk = foreign_key_for(AttachedCertificate, "certification_id")

    assert certification_fk.ondelete == "CASCADE"
    assert certification_fk.deferrable is True
    assert has_unique_constraint(AttachedCertificate, ["certification_id"])


def test_uploaded_at_has_a_database_default() -> None:
    assert (
        str(AttachedCertificate.__table__.c.uploaded_at.server_default.arg) == "now()"
    )
