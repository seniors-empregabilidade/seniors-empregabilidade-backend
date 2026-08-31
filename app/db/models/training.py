from sqlalchemy import Boolean, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import Timestamps, UUIDPrimaryKey
from app.db.models.enums import TrainingMode, enum_type


class Training(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "training"

    title: Mapped[str] = mapped_column(String(150))
    provider: Mapped[str | None] = mapped_column(String(150))
    area: Mapped[str | None] = mapped_column(String(100))
    training_mode: Mapped[TrainingMode | None] = mapped_column(
        enum_type(TrainingMode, "training_mode")
    )
    workload_hours: Mapped[int | None] = mapped_column(SmallInteger)
    free: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    external_link: Mapped[str] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), index=True
    )
