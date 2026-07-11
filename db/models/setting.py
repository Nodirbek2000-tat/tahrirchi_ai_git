from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Setting(Base):
    """Kalit-qiymat sozlamalari (masalan, AI xarajati hisoblagichi)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[float] = mapped_column(Float, default=0.0)
