from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InterviewScore(Base):
    """Immutable by design: no updated_at, no edit/delete path anywhere. Written once,
    atomically, alongside every other Score for a Candidate's submission."""

    __tablename__ = "interview_scores"
    __table_args__ = (
        CheckConstraint("score BETWEEN 1 AND 5", name="ck_interview_score_range"),
        UniqueConstraint("round_id", "question_id", name="uq_interview_score_round_question"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidates.id"), nullable=False)
    round_id: Mapped[int] = mapped_column(Integer, ForeignKey("rounds.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
