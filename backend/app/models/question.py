from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("position_id", "sequence_order", name="uq_question_position_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(Integer, ForeignKey("positions.id"), nullable=False)
    question_text: Mapped[str] = mapped_column(String, nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
