"""Add missing notes column to inventory_movements

The live table was missing this column even though it has existed on the
InventoryMovement model since the baseline. Applied directly against Neon
and recorded here for history.

Revision ID: 0002_inventory_movements_notes
Revises: 0001_initial_schema
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_inventory_movements_notes"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_movements", sa.Column("notes", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_movements", "notes")
