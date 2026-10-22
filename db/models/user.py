from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from data import config
from db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram id
    full_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    free_files: Mapped[int] = mapped_column(Integer, default=config.FREE_FILES)
    free_texts: Mapped[int] = mapped_column(Integer, default=config.FREE_TEXTS)
    premium_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_blocked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @property
    def is_premium(self) -> bool:
        return self.premium_until is not None and self.premium_until > datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<User id={self.id} free_files={self.free_files} premium={self.premium_until}>"
