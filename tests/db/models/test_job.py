from sqlalchemy.dialects.postgresql import JSONB

from app.db.models import Job


def test_desired_skills_use_postgresql_jsonb() -> None:
    assert isinstance(Job.__table__.c.desired_skills.type, JSONB)
