"""Add product bundles (kits): is_bundle flag + product_components table.

A "kit" product (e.g. "Jarabe pack x2") never carries its own inventory
row — it's composed of `qty` units of a base product ("Jarabe individual")
and its available stock is derived from that component's stock at read
time. Selling a kit deducts from the component instead of the kit itself.

Applied directly against Neon; recorded here for history.

Revision ID: 0004_product_bundles
Revises: 0003_multi_tenant
Create Date: 2026-07-05
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_product_bundles"
down_revision = "0003_multi_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("is_bundle", sa.Boolean, nullable=False, server_default=sa.false()))
    op.create_table(
        "product_components",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("bundle_product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("component_product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
    )
    op.create_index("idx_product_components_bundle", "product_components", ["bundle_product_id"])


def downgrade() -> None:
    op.drop_index("idx_product_components_bundle", table_name="product_components")
    op.drop_table("product_components")
    op.drop_column("products", "is_bundle")
