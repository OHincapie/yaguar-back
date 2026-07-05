"""Add AI agents infrastructure: config, alerts, event trigger queue, and
due_date on sales (needed by the collections agent to know when a credit
sale is overdue).

Applied directly against Neon; recorded here for history.

Revision ID: 0005_ai_agents
Revises: 0004_product_bundles
Create Date: 2026-07-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_ai_agents"
down_revision = "0004_product_bundles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales", sa.Column("due_date", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "agent_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("agent_key", sa.String(length=20), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("autonomy", sa.String(length=10), nullable=False, server_default="ask"),
        sa.Column("auto_limit", sa.Float, nullable=True),
        sa.UniqueConstraint("company_id", "agent_key", name="uq_agent_configs_company_agent"),
    )

    op.create_table(
        "agent_alerts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("agent_key", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("context", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("proposed_action", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("thread_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_agent_alerts_company", "agent_alerts", ["company_id", "status"])

    op.create_table(
        "pending_agent_triggers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("agent_key", sa.String(length=20), nullable=False),
        sa.Column("context", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_pending_triggers_unprocessed",
        "pending_agent_triggers",
        ["company_id"],
        postgresql_where=sa.text("processed_at IS NULL"),
    )

    # LangGraph's Postgres checkpointer (checkpoints/checkpoint_writes/
    # checkpoint_blobs/checkpoint_migrations) is created by calling
    # AsyncPostgresSaver.setup() at app startup, not by this migration —
    # it owns its own schema versioning.


def downgrade() -> None:
    op.drop_table("pending_agent_triggers")
    op.drop_index("idx_agent_alerts_company", table_name="agent_alerts")
    op.drop_table("agent_alerts")
    op.drop_table("agent_configs")
    op.drop_column("sales", "due_date")
