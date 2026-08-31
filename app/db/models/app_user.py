from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import Timestamps, UUIDPrimaryKey
from app.db.models.enums import AccountStatus, UserType, enum_type


class AppUser(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "app_user"

    email: Mapped[str] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    user_type: Mapped[UserType] = mapped_column(
        enum_type(UserType, "user_type"), index=True
    )
    account_status: Mapped[AccountStatus] = mapped_column(
        enum_type(AccountStatus, "account_status"),
        server_default=AccountStatus.ACTIVE.value,
    )
