"""add pipeline stages and candidate stage transitions

Revision ID: 9f1c2a7d4b6e
Revises: 25b8fba82dc0
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9f1c2a7d4b6e'
down_revision: Union[str, None] = '25b8fba82dc0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (name, sequence_order, day_limit) — must match app/pipeline/stages.py DEFAULT_STAGES.
DEFAULT_STAGES = [
    ("Applied", 1, 3),
    ("Screening", 2, 5),
    ("Under review", 3, 5),
    ("Offer", 4, 3),
    ("Hired", 5, None),
    ("Rejected", 6, None),
]


def upgrade() -> None:
    op.create_table(
        "stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("day_limit", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("position_id", "sequence_order", name="uq_stage_position_sequence"),
    )

    op.create_table(
        "candidate_stage_transitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_stage_id", sa.Integer(), sa.ForeignKey("stages.id"), nullable=True),
        sa.Column("to_stage_id", sa.Integer(), sa.ForeignKey("stages.id"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    connection = op.get_bind()

    # Seed the default pipeline for every position that already exists.
    position_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM positions")).fetchall()]
    stages_table = sa.table(
        "stages",
        sa.column("position_id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("sequence_order", sa.Integer()),
        sa.column("day_limit", sa.Integer()),
    )
    for position_id in position_ids:
        op.bulk_insert(
            stages_table,
            [
                {"position_id": position_id, "name": name, "sequence_order": order, "day_limit": day_limit}
                for name, order, day_limit in DEFAULT_STAGES
            ],
        )

    # Backfill an initial transition (into "Applied") for every existing candidate,
    # dated at the candidate's own created_at so days-in-stage reflects reality
    # instead of the migration's run time.
    connection.execute(
        sa.text(
            """
            INSERT INTO candidate_stage_transitions (candidate_id, from_stage_id, to_stage_id, actor_id, created_at)
            SELECT c.id, NULL, s.id, c.created_by, c.created_at
            FROM candidates c
            JOIN stages s ON s.position_id = c.position_id AND s.sequence_order = 1
            """
        )
    )


def downgrade() -> None:
    op.drop_table("candidate_stage_transitions")
    op.drop_table("stages")
