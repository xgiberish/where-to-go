"""add destination column and tool_calls table

Revision ID: d3e4f5a6b7c8
Revises: f44c2394de4e
Create Date: 2026-05-01 00:00:00.000000

Changes:
- embeddings: add destination VARCHAR(255) column, backfill from metadata JSON
- tool_calls: new table linking tool executions to agent_runs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "f44c2394de4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── embeddings: explicit destination column ───────────────────────────────
    # server_default='' handles existing rows; we then backfill from metadata JSON
    op.add_column(
        "embeddings",
        sa.Column("destination", sa.String(255), nullable=False, server_default=""),
    )
    # Backfill from existing metadata JSON (PostgreSQL ->> operator works on json type)
    op.execute(
        "UPDATE embeddings SET destination = metadata->>'destination' "
        "WHERE metadata->>'destination' IS NOT NULL AND metadata->>'destination' != ''"
    )

    # ── tool_calls: one row per tool execution linked to an agent_run ─────────
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("input", sa.JSON(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tool_calls_agent_run_id", "tool_calls", ["agent_run_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_tool_calls_agent_run_id", table_name="tool_calls")
    op.drop_table("tool_calls")
    op.drop_column("embeddings", "destination")
