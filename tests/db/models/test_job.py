from sqlalchemy.dialects.postgresql import JSONB

from app.db.models import Job
from tests.db.models.assertions import foreign_key_for, has_index


def test_desired_skills_use_postgresql_jsonb() -> None:
    assert isinstance(Job.__table__.c.desired_skills.type, JSONB)


def test_company_foreign_key_cascades_and_is_indexed() -> None:
    company_fk = foreign_key_for(Job, "company_id")

    assert company_fk.ondelete == "CASCADE"
    assert company_fk.deferrable is True
    assert has_index(Job, "ix_job_company_id")


def test_job_defaults_and_status_index_are_declared() -> None:
    assert Job.__table__.c.status.server_default.arg == "draft"
    assert str(Job.__table__.c.featured.server_default.arg) == "false"
    assert str(Job.__table__.c.desired_skills.server_default.arg) == "'[]'::jsonb"
    assert has_index(Job, "ix_job_status")
