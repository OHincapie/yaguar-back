"""Add ai_usage_events table.

Tracks raw token/audio-duration usage per AI call (chat, transcription,
agent runs) so spend can be monitored — no dollar amount stored, that's
computed at query time from a pricing table kept in code, since prices
change and a stored $ figure would go stale.

Applied directly against Neon; recorded here for history.

Revision ID: 0010_ai_usage_events
Revises: 0009_must_change_password
Create Date: 2026-07-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_ai_usage_events"
down_revision = "0009_must_change_password"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False, server_default="openai"),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("cached_input_tokens", sa.Integer, nullable=True),
        sa.Column("audio_seconds", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_usage_events_company_id", "ai_usage_events", ["company_id"])
    op.create_index("ix_ai_usage_events_source", "ai_usage_events", ["source"])
    op.create_index("ix_ai_usage_events_model", "ai_usage_events", ["model"])
    op.create_index("ix_ai_usage_events_created_at", "ai_usage_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("ai_usage_events")
