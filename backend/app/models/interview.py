import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InterviewStatus(str, enum.Enum):
    scheduled = "scheduled"
    cancelled = "cancelled"


class Interview(Base):
    """A scheduled meeting for one Round — the calendar's unit of data.
    Deliberately independent of the Stage/pipeline system: scheduling doesn't
    move a candidate anywhere by itself, an admin still does that on the board.
    Only an admin creates/cancels these — an Interviewer can see their own but
    never another's, and never another candidate's.

    Cancelling sets status='cancelled' rather than deleting the row — every
    read path must filter status != 'cancelled' or a cancelled interview
    reappears."""

    __tablename__ = "interviews"
    __table_args__ = (
        Index(
            "uq_interviews_round_active",
            "round_id",
            unique=True,
            postgresql_where=text("status != 'cancelled'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    round_id: Mapped[int] = mapped_column(Integer, ForeignKey("rounds.id"), nullable=False)
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, name="interview_status"),
        nullable=False,
        server_default=InterviewStatus.scheduled.value,
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60")
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
