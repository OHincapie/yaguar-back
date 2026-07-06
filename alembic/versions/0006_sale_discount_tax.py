"""Add real discount/tax to sales, and per-company POS defaults.

Previously the 5%/18% shown on the POS receipt were purely a frontend
display — the backend only ever recorded qty*unit_price with no
discount or tax. This makes them real: Company gets configurable
discount_pct/tax_pct (+ enabled flags) and Sale stores the computed
subtotal/discount_amount/tax_amount alongside total, so a sale's
numbers don't drift if the company's settings change later.

Applied directly against Neon; recorded here for history.

Revision ID: 0006_sale_discount_tax
Revises: 0005_ai_agents
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_sale_discount_tax"
down_revision = "0005_ai_agents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("discount_enabled", sa.Boolean, nullable=False, server_default=sa.true()))
    op.add_column("companies", sa.Column("discount_pct", sa.Float, nullable=False, server_default="5.0"))
    op.add_column("companies", sa.Column("tax_enabled", sa.Boolean, nullable=False, server_default=sa.true()))
    op.add_column("companies", sa.Column("tax_pct", sa.Float, nullable=False, server_default="18.0"))

    op.add_column("sales", sa.Column("subtotal", sa.Float, nullable=False, server_default="0.0"))
    op.add_column("sales", sa.Column("discount_amount", sa.Float, nullable=False, server_default="0.0"))
    op.add_column("sales", sa.Column("tax_amount", sa.Float, nullable=False, server_default="0.0"))
    # Existing sales' `total` was already the raw subtotal (no discount/tax
    # ever applied), so backfilling subtotal=total keeps their numbers
    # consistent with the new columns' meaning.
    op.execute("UPDATE sales SET subtotal = total")


def downgrade() -> None:
    op.drop_column("sales", "tax_amount")
    op.drop_column("sales", "discount_amount")
    op.drop_column("sales", "subtotal")
    op.drop_column("companies", "tax_pct")
    op.drop_column("companies", "tax_enabled")
    op.drop_column("companies", "discount_pct")
    op.drop_column("companies", "discount_enabled")
