import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class TaskStatus(str, enum.Enum):
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Task(Base):
    """Tahrir qilingan fayllar tarixi."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    file_name: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(16))
    tokens_spent: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PROCESSING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
