"""add llm call tracking

Revision ID: f44c2394de4e
Revises: 5030e0a1a962
Create Date: 2026-04-29 17:22:37.570311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f44c2394de4e"
down_revision: Union[str, None] = "5030e0a1a962"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=False),
        sa.Column("call_type", sa.String(length=50), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("actual_cost_usd", sa.Numeric(precision=10, scale=8), nullable=False),
        sa.Column(
            "hypothetical_claude_haiku_cost",
            sa.Numeric(precision=10, scale=8),
            nullable=False,
        ),
        sa.Column(
            "hypothetical_claude_sonnet_cost",
            sa.Numeric(precision=10, scale=8),
            nullable=False,
        ),
        sa.Column(
            "hypothetical_gemini_flash_cost",
            sa.Numeric(precision=10, scale=8),
            nullable=False,
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_llm_calls_agent_run_id"),
        "llm_calls",
        ["agent_run_id"],
        unique=False,
    )

    # server_default="0" protects existing agent_run rows during migration.
    op.add_column(
        "agent_runs",
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "total_actual_cost",
            sa.Numeric(precision=10, scale=8),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "total_hypothetical_claude_cost",
            sa.Numeric(precision=10, scale=8),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "total_hypothetical_gemini_cost",
            sa.Numeric(precision=10, scale=8),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "total_hypothetical_gemini_cost")
    op.drop_column("agent_runs", "total_hypothetical_claude_cost")
    op.drop_column("agent_runs", "total_actual_cost")
    op.drop_column("agent_runs", "total_tokens")

    op.drop_index(op.f("ix_llm_calls_agent_run_id"), table_name="llm_calls")
    op.drop_table("llm_calls")