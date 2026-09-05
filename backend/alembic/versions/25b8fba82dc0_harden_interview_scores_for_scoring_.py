"""harden interview_scores for scoring submit

Revision ID: 25b8fba82dc0
Revises: 036ce18bb9e9
Create Date: 2026-09-01 22:21:13.204902

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '25b8fba82dc0'
down_revision: Union[str, None] = '036ce18bb9e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('interview_scores', 'submitted_at', new_column_name='created_at')
    op.create_foreign_key(
        'fk_interview_scores_candidate_id_candidates',
        'interview_scores',
        'candidates',
        ['candidate_id'],
        ['id'],
    )
    op.create_unique_constraint(
        'uq_interview_score_candidate_question', 'interview_scores', ['candidate_id', 'question_id']
    )
    op.create_check_constraint(
        'ck_interview_score_range', 'interview_scores', 'score BETWEEN 1 AND 5'
    )


def downgrade() -> None:
    op.drop_constraint('ck_interview_score_range', 'interview_scores', type_='check')
    op.drop_constraint('uq_interview_score_candidate_question', 'interview_scores', type_='unique')
    op.drop_constraint('fk_interview_scores_candidate_id_candidates', 'interview_scores', type_='foreignkey')
    op.alter_column('interview_scores', 'created_at', new_column_name='submitted_at')
