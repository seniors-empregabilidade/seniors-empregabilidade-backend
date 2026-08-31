from sqlalchemy import CHAR, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import CreatedAt, UUIDPrimaryKey


class Address(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "address"

    street: Mapped[str] = mapped_column(String(150))
    number: Mapped[str] = mapped_column(String(10))
    complement: Mapped[str | None] = mapped_column(String(100))
    neighborhood: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(CHAR(2))
    zip_code: Mapped[str] = mapped_column(CHAR(8))
    code: Mapped[str | None] = mapped_column(String(20))
