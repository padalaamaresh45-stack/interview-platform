import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RoundStatus(str, enum.Enum):
    open = "open"
    scored = "scored"
    reassigned = "reassigned"
    closed_unscored = "closed_unscored"


class Round(Base):
    """One Candidate's assignment to one Stage with one interviewer — the unit
    ownership, access, and scoring are all scoped to. A Candidate accrues one
    Round per stage/reassignment; `compute_current_owner` (app/pipeline/derive.py)
    reads only the single `open` Round a candidate may have at a time, enforced
    at the database level by the partial unique index on (candidate_id) WHERE
    status='open' — never derive "current owner" any other way."""

    __tablename__ = "rounds"
    __table_args__ = (
        Index(
            "uq_rounds_candidate_open",
            "candidate_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    stage_id: Mapped[int] = mapped_column(Integer, ForeignKey("stages.id"), nullable=False)
    assignee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    status: Mapped[RoundStatus] = mapped_column(
        Enum(RoundStatus, name="round_status"), nullable=False, server_default=RoundStatus.open.value
    )
    assignment_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    brief: Mapped[str | None] = mapped_column(String, nullable=True)
    reassigned_from_round_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("rounds.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
