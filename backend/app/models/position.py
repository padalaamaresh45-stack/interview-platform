from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, event, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


@event.listens_for(Position, "after_insert")
def _seed_default_stages(mapper, connection, position: "Position") -> None:
    """Every Position must have a pipeline the moment it exists — candidate
    creation depends on a first stage existing. Seeding here, at the model
    layer, means every insert path (the admin router, test fixtures, future
    scripts) gets it for free; seeding only in the router left test-fixture
    positions without stages and candidate creation broke under them."""
    from app.models.stage import Stage
    from app.pipeline.stages import DEFAULT_STAGES

    connection.execute(
        Stage.__table__.insert(),
        [
            {
                "position_id": position.id,
                "name": name,
                "sequence_order": sequence_order,
                "day_limit": day_limit,
            }
            for sequence_order, (name, day_limit) in enumerate(DEFAULT_STAGES, start=1)
        ],
    )
