"""add rounds table; split Candidate/Interview interviewer_id into Round;
interview status + soft-cancel; interview_scores round_id

Revision ID: f1a2b3c4d5e6
Revises: c4d8e91f2a3b
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'c4d8e91f2a3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    round_status = sa.Enum("open", "scored", "reassigned", "closed_unscored", name="round_status")
    interview_status = sa.Enum("scheduled", "cancelled", name="interview_status", create_type=False)
    interview_status.create(op.get_bind(), checkfirst=True)

    # 1. rounds table + its partial unique index (one open round per candidate)
    op.create_table(
        "rounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", sa.Integer(), sa.ForeignKey("stages.id"), nullable=False),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", round_status, nullable=False, server_default="open"),
        sa.Column("assignment_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("brief", sa.String(), nullable=True),
        sa.Column("reassigned_from_round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_rounds_candidate_open",
        "rounds",
        ["candidate_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )

    # 2. backfill one Round per existing candidate: assignee = old interviewer_id,
    # stage = candidate's current (latest transition) stage, status = open.
    op.execute(
        sa.text(
            """
            INSERT INTO rounds (candidate_id, stage_id, assignee_id, status, created_at)
            SELECT c.id, latest.to_stage_id, c.interviewer_id, 'open', c.created_at
            FROM candidates c
            JOIN LATERAL (
                SELECT to_stage_id
                FROM candidate_stage_transitions t
                WHERE t.candidate_id = c.id
                ORDER BY t.created_at DESC, t.id DESC
                LIMIT 1
            ) latest ON true
            """
        )
    )

    # 3. interviews: add round_id (nullable), status; backfill; then tighten.
    op.add_column("interviews", sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=True))
    op.add_column(
        "interviews",
        sa.Column("status", interview_status, nullable=False, server_default="scheduled"),
    )
    op.execute(
        sa.text(
            """
            UPDATE interviews i
            SET round_id = r.id
            FROM rounds r
            WHERE r.candidate_id = i.candidate_id
            """
        )
    )
    op.alter_column("interviews", "round_id", nullable=False)
    op.drop_column("interviews", "interviewer_id")

    # Pre-existing data may have scheduled more than one interview against what
    # is now the same Round (the new active-per-round uniqueness didn't exist
    # yet). Keep only the most recently created one active; the invariant this
    # ticket introduces has to hold before its enforcing index can be created.
    op.execute(
        sa.text(
            """
            UPDATE interviews
            SET status = 'cancelled'
            WHERE id NOT IN (
                SELECT DISTINCT ON (round_id) id
                FROM interviews
                ORDER BY round_id, created_at DESC, id DESC
            )
            """
        )
    )
    op.create_index(
        "uq_interviews_round_active",
        "interviews",
        ["round_id"],
        unique=True,
        postgresql_where=sa.text("status != 'cancelled'"),
    )

    # 4. interview_scores: add round_id (nullable), backfill, tighten, swap constraint.
    op.add_column(
        "interview_scores", sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=True)
    )
    op.execute(
        sa.text(
            """
            UPDATE interview_scores s
            SET round_id = r.id
            FROM rounds r
            WHERE r.candidate_id = s.candidate_id
            """
        )
    )
    op.alter_column("interview_scores", "round_id", nullable=False)
    op.drop_constraint("uq_interview_score_candidate_question", "interview_scores", type_="unique")
    op.create_unique_constraint(
        "uq_interview_score_round_question", "interview_scores", ["round_id", "question_id"]
    )

    # 5. candidates: drop interviewer_id, add hold_* columns.
    op.drop_column("candidates", "interviewer_id")
    op.add_column("candidates", sa.Column("hold_reason", sa.String(), nullable=True))
    op.add_column("candidates", sa.Column("hold_review_by", sa.Date(), nullable=True))

    # 6. stages: routing thresholds (ticket #27's logic, schema added together).
    op.add_column("stages", sa.Column("advance_threshold", sa.Integer(), nullable=True))
    op.add_column("stages", sa.Column("reject_threshold", sa.Integer(), nullable=True))
    op.add_column(
        "stages", sa.Column("feedback_grace_hours", sa.Integer(), nullable=True, server_default="48")
    )

    # 7. users: timezone (schema only, ticket #29's logic).
    op.add_column("users", sa.Column("timezone", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "timezone")

    op.drop_column("stages", "feedback_grace_hours")
    op.drop_column("stages", "reject_threshold")
    op.drop_column("stages", "advance_threshold")

    op.add_column("candidates", sa.Column("interviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE candidates c
            SET interviewer_id = r.assignee_id
            FROM rounds r
            WHERE r.candidate_id = c.id AND r.status = 'open'
            """
        )
    )
    op.alter_column("candidates", "interviewer_id", nullable=False)
    op.drop_column("candidates", "hold_review_by")
    op.drop_column("candidates", "hold_reason")

    op.drop_constraint("uq_interview_score_round_question", "interview_scores", type_="unique")
    op.create_unique_constraint(
        "uq_interview_score_candidate_question", "interview_scores", ["candidate_id", "question_id"]
    )
    op.drop_column("interview_scores", "round_id")

    op.drop_index("uq_interviews_round_active", table_name="interviews")
    op.add_column("interviews", sa.Column("interviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE interviews i
            SET interviewer_id = r.assignee_id
            FROM rounds r
            WHERE r.id = i.round_id
            """
        )
    )
    op.alter_column("interviews", "interviewer_id", nullable=False)
    op.drop_column("interviews", "status")
    op.drop_column("interviews", "round_id")

    op.drop_index("uq_rounds_candidate_open", table_name="rounds")
    op.drop_table("rounds")

    sa.Enum(name="interview_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="round_status").drop(op.get_bind(), checkfirst=True)
