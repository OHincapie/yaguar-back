"""Baseline: reflects the schema already provisioned on Neon.

This project's tables were originally created via SQLModel's
``metadata.create_all`` (see src/seed.py / src/shared/database.py) before
Alembic was wired up, so no migration history existed even though the
database was fully provisioned and seeded. This revision captures that
existing schema as the Alembic baseline and is applied via ``alembic
stamp`` rather than ``alembic upgrade`` (the tables already exist).

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.String(length=50), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False, server_default="#6B7280"),
    )

    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(length=50), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("contact", sa.String(length=200), nullable=True),
        sa.Column("categories", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("rating", sa.Float, nullable=True, server_default="0.0"),
        sa.Column("lead_days", sa.Integer, nullable=True, server_default="7"),
        sa.Column("saldo", sa.Float, nullable=True, server_default="0.0"),
        sa.Column("status", sa.String(length=20), nullable=True, server_default="activo"),
        sa.Column("on_time_pct", sa.Float, nullable=True, server_default="0.0"),
        sa.Column("orders_count", sa.Integer, nullable=True, server_default="0"),
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=50), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=True, server_default="minorista"),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("ltv", sa.Float, nullable=True, server_default="0.0"),
        sa.Column("status", sa.String(length=20), nullable=True, server_default="activo"),
        sa.Column("saldo", sa.Float, nullable=True, server_default="0.0"),
        sa.Column("orders", sa.Integer, nullable=True, server_default="0"),
    )

    op.create_table(
        "products",
        sa.Column("sku", sa.String(length=50), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "category_id",
            sa.String(length=50),
            sa.ForeignKey("categories.id"),
            nullable=True,
        ),
        sa.Column("price", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("cost", sa.Float, nullable=False, server_default="0.0"),
        sa.Column(
            "supplier_id",
            sa.String(length=50),
            sa.ForeignKey("suppliers.id"),
            nullable=True,
        ),
        sa.Column("unit", sa.String(length=50), nullable=True, server_default="unidad"),
    )

    op.create_table(
        "inventory_levels",
        sa.Column(
            "product_sku",
            sa.String(length=50),
            sa.ForeignKey("products.sku"),
            primary_key=True,
        ),
        sa.Column("stock_qty", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("min_stock", sa.Float, nullable=False, server_default="0.0"),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "product_sku",
            sa.String(length=50),
            sa.ForeignKey("products.sku"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column(
            "date", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()
        ),
        sa.Column("notes", sa.String(length=500), nullable=True),
    )

    op.create_table(
        "purchases",
        sa.Column("id", sa.String(length=50), primary_key=True),
        sa.Column(
            "supplier_id",
            sa.String(length=50),
            sa.ForeignKey("suppliers.id"),
            nullable=False,
        ),
        sa.Column(
            "date", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()
        ),
        sa.Column("total", sa.Float, nullable=True, server_default="0.0"),
        sa.Column("status", sa.String(length=20), nullable=True, server_default="borrador"),
        sa.Column("eta", sa.Date, nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
    )

    op.create_table(
        "purchase_lines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "purchase_id",
            sa.String(length=50),
            sa.ForeignKey("purchases.id"),
            nullable=False,
        ),
        sa.Column(
            "product_sku",
            sa.String(length=50),
            sa.ForeignKey("products.sku"),
            nullable=False,
        ),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("unit_cost", sa.Float, nullable=False),
    )

    op.create_table(
        "sales",
        sa.Column("id", sa.String(length=50), primary_key=True),
        sa.Column(
            "customer_id",
            sa.String(length=50),
            sa.ForeignKey("customers.id"),
            nullable=True,
        ),
        sa.Column(
            "date", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()
        ),
        sa.Column("total", sa.Float, nullable=True, server_default="0.0"),
        sa.Column(
            "payment_method", sa.String(length=50), nullable=True, server_default="Efectivo"
        ),
        sa.Column("status", sa.String(length=20), nullable=True, server_default="pendiente"),
        sa.Column("notes", sa.String(length=500), nullable=True),
    )

    op.create_table(
        "sale_lines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "sale_id", sa.String(length=50), sa.ForeignKey("sales.id"), nullable=False
        ),
        sa.Column(
            "product_sku",
            sa.String(length=50),
            sa.ForeignKey("products.sku"),
            nullable=False,
        ),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("unit_price", sa.Float, nullable=False),
        sa.Column("unit_cost", sa.Float, nullable=False),
    )

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "date", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()
        ),
        sa.Column("concept", sa.String(length=300), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("debit", sa.Float, nullable=True, server_default="0.0"),
        sa.Column("credit", sa.Float, nullable=True, server_default="0.0"),
        sa.Column("type", sa.String(length=20), nullable=True, server_default="out"),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ledger_entries")
    op.drop_table("sale_lines")
    op.drop_table("sales")
    op.drop_table("purchase_lines")
    op.drop_table("purchases")
    op.drop_table("inventory_movements")
    op.drop_table("inventory_levels")
    op.drop_table("products")
    op.drop_table("customers")
    op.drop_table("suppliers")
    op.drop_table("categories")
