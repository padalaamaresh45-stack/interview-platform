from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CandidateStageTransition(Base):
    """Immutable, append-only: a candidate's current stage is the to_stage_id of its
    most recent transition (highest id / created_at). Never update or delete a row
    here — moving a candidate always inserts a new one, which is what gives us an
    audit trail and days-in-stage for free from a single write."""

    __tablename__ = "candidate_stage_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    from_stage_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("stages.id"), nullable=True)
    to_stage_id: Mapped[int] = mapped_column(Integer, ForeignKey("stages.id"), nullable=False)
    actor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
