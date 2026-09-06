from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Stage(Base):
    """One ordered step of a position's pipeline. sequence_order is 1-based and
    unique per position; day_limit (in whole days) is the threshold health is
    derived from — null means no limit is enforced for that stage. is_terminal
    marks a stage that ends the pipeline (Hired, Rejected) — health/next-action
    derivation and the move guard key off this, not the stage name."""

    __tablename__ = "stages"
    __table_args__ = (UniqueConstraint("position_id", "sequence_order", name="uq_stage_position_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(Integer, ForeignKey("positions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    day_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
