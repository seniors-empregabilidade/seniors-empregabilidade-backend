from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import CreatedAt, UUIDPrimaryKey
from app.db.models.enums import SkillType, enum_type


class Skill(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "skill"
    __table_args__ = (UniqueConstraint("name", "type"),)

    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[SkillType] = mapped_column(enum_type(SkillType, "skill_type"))
