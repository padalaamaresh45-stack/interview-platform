"""add stage.is_terminal, backfill true for Hired/Rejected

Revision ID: c4d8e91f2a3b
Revises: b3f7a2c9d1e4
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4d8e91f2a3b'
down_revision: Union[str, None] = 'b3f7a2c9d1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TERMINAL_STAGE_NAMES = ("Hired", "Rejected")


def upgrade() -> None:
    op.add_column(
        "stages",
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    stages = sa.table(
        "stages",
        sa.column("name", sa.String),
        sa.column("is_terminal", sa.Boolean),
    )
    op.execute(
        stages.update()
        .where(stages.c.name.in_(TERMINAL_STAGE_NAMES))
        .values(is_terminal=True)
    )


def downgrade() -> None:
    op.drop_column("stages", "is_terminal")
