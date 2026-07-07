"""Add per-user module access (UserCompany.modules).

Lets an owner/admin restrict a "member" user to specific modules
(inventario, ventas, compras, etc. — see accounts.models.MODULE_KEYS).
Owner/admin always have full access regardless of this list.

Applied directly against Neon; recorded here for history.

Revision ID: 0007_user_modules
Revises: 0006_sale_discount_tax
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_user_modules"
down_revision = "0006_sale_discount_tax"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_companies", sa.Column("modules", postgresql.JSONB, nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("user_companies", "modules")
