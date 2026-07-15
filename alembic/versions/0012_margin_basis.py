"""Add Company.margin_basis (configurable margin convention).

"price" (gross margin over sale price, the prior/default behavior) or
"cost" (markup over cost). Picked per company and applied everywhere a
margin percentage is shown — Inventario, Dashboard KPIs, Kuri the margins
agent — via src/shared/margin.py.

Applied directly against Neon; recorded here for history.

Revision ID: 0012_margin_basis
Revises: 0011_cartera
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_margin_basis"
down_revision = "0011_cartera"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("margin_basis", sa.String, nullable=False, server_default="price"))


def downgrade() -> None:
    op.drop_column("companies", "margin_basis")
