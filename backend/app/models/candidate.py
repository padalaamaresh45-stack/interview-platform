import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, event, func, select
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CandidateStatus(str, enum.Enum):
    not_started = "not_started"
    completed = "completed"


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    position_id: Mapped[int] = mapped_column(Integer, ForeignKey("positions.id"), nullable=False)
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus, name="candidate_status"),
        nullable=False,
        server_default=CandidateStatus.not_started.value,
    )
    hold_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    hold_review_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


@event.listens_for(Candidate, "after_insert")
def _seed_initial_stage_transition(mapper, connection, candidate: "Candidate") -> None:
    """Every Candidate must enter the pipeline at its position's first stage the
    moment it exists — see the matching Position.after_insert event for why this
    lives at the model layer instead of only in the admin router: a candidate
    created any other way (a test fixture, a future script) still needs a current
    stage, or it silently drops off the board and the candidate page can't render
    a history."""
    from app.models.stage import Stage
    from app.models.stage_transition import CandidateStageTransition

    first_stage_id = connection.execute(
        select(Stage.id)
        .where(Stage.position_id == candidate.position_id)
        .order_by(Stage.sequence_order)
        .limit(1)
    ).scalar()
    if first_stage_id is None:
        return

    connection.execute(
        CandidateStageTransition.__table__.insert(),
        [
            {
                "candidate_id": candidate.id,
                "from_stage_id": None,
                "to_stage_id": first_stage_id,
                "actor_id": candidate.created_by,
            }
        ],
    )
