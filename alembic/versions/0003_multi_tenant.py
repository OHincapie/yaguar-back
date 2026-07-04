"""Multi-tenant: companies/users + UUID surrogate keys per business entity.

Introduces companies, users, and user_companies (many-to-many with role).
Every business table gains a company_id FK. Entities that previously used
a human-chosen string as their primary key (categories, products,
suppliers, customers, sales, purchases) now use a generated UUID as the
primary key instead, with the human-facing value moved to a `code` column
(or `sku` for products) that's unique per company instead of globally.
This avoids collisions when two different companies independently choose
the same code (e.g. both naming a product "TEC-1180").

This was applied directly against Neon (see conversation history) since
the affected tables already had data; this revision documents that
end-state schema for fresh installs.

Revision ID: 0003_multi_tenant
Revises: 0002_inventory_movements_notes
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_multi_tenant"
down_revision = "0002_inventory_movements_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "user_companies",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), primary_key=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- categories: id (code) -> code, new UUID id ---
    op.drop_constraint("products_category_id_fkey", "products", type_="foreignkey")
    op.alter_column("categories", "id", new_column_name="code")
    op.drop_constraint("categories_pkey", "categories")
    op.add_column("categories", sa.Column("id", sa.String(length=36), server_default=sa.text("gen_random_uuid()::text")))
    op.execute("UPDATE categories SET id = gen_random_uuid()::text WHERE id IS NULL")
    op.alter_column("categories", "id", nullable=False)
    op.create_primary_key("categories_pkey", "categories", ["id"])
    op.add_column("categories", sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id")))
    op.create_unique_constraint("uq_categories_company_code", "categories", ["company_id", "code"])

    # --- suppliers: id (code) -> code, new UUID id ---
    op.drop_constraint("products_supplier_id_fkey", "products", type_="foreignkey")
    op.drop_constraint("purchases_supplier_id_fkey", "purchases", type_="foreignkey")
    op.alter_column("suppliers", "id", new_column_name="code")
    op.drop_constraint("suppliers_pkey", "suppliers")
    op.add_column("suppliers", sa.Column("id", sa.String(length=36), server_default=sa.text("gen_random_uuid()::text")))
    op.execute("UPDATE suppliers SET id = gen_random_uuid()::text WHERE id IS NULL")
    op.alter_column("suppliers", "id", nullable=False)
    op.create_primary_key("suppliers_pkey", "suppliers", ["id"])
    op.add_column("suppliers", sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id")))
    op.create_unique_constraint("uq_suppliers_company_code", "suppliers", ["company_id", "code"])

    # --- customers: id (code) -> code, new UUID id ---
    op.drop_constraint("sales_customer_id_fkey", "sales", type_="foreignkey")
    op.alter_column("customers", "id", new_column_name="code")
    op.drop_constraint("customers_pkey", "customers")
    op.add_column("customers", sa.Column("id", sa.String(length=36), server_default=sa.text("gen_random_uuid()::text")))
    op.execute("UPDATE customers SET id = gen_random_uuid()::text WHERE id IS NULL")
    op.alter_column("customers", "id", nullable=False)
    op.create_primary_key("customers_pkey", "customers", ["id"])
    op.add_column("customers", sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id")))
    op.create_unique_constraint("uq_customers_company_code", "customers", ["company_id", "code"])

    # --- products: sku stays, new UUID id; repoint category_id/supplier_id ---
    op.drop_constraint("inventory_levels_product_sku_fkey", "inventory_levels", type_="foreignkey")
    op.drop_constraint("inventory_movements_product_sku_fkey", "inventory_movements", type_="foreignkey")
    op.drop_constraint("purchase_lines_product_sku_fkey", "purchase_lines", type_="foreignkey")
    op.drop_constraint("sale_lines_product_sku_fkey", "sale_lines", type_="foreignkey")
    op.drop_constraint("products_pkey", "products")
    op.add_column("products", sa.Column("id", sa.String(length=36), server_default=sa.text("gen_random_uuid()::text")))
    op.execute("UPDATE products SET id = gen_random_uuid()::text WHERE id IS NULL")
    op.alter_column("products", "id", nullable=False)
    op.create_primary_key("products_pkey", "products", ["id"])
    op.add_column("products", sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id")))
    # NOTE: on a fresh install these UPDATE/backfill statements are no-ops
    # (no rows exist yet); on the live Neon DB they were run manually with
    # an explicit company_id before this file was written.
    op.create_foreign_key("products_category_id_fkey", "products", "categories", ["category_id"], ["id"])
    op.create_foreign_key("products_supplier_id_fkey", "products", "suppliers", ["supplier_id"], ["id"])
    op.create_unique_constraint("uq_products_company_sku", "products", ["company_id", "sku"])

    # --- inventory_levels: product_sku -> product_id (FK to products.id) ---
    op.drop_constraint("inventory_levels_pkey", "inventory_levels")
    op.alter_column("inventory_levels", "product_sku", new_column_name="product_id", type_=sa.String(length=36))
    op.add_column("inventory_levels", sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id")))
    op.create_primary_key("inventory_levels_pkey", "inventory_levels", ["product_id"])
    op.create_foreign_key("inventory_levels_product_id_fkey", "inventory_levels", "products", ["product_id"], ["id"])

    # --- inventory_movements: product_sku -> product_id, add company_id ---
    op.alter_column("inventory_movements", "product_sku", new_column_name="product_id", type_=sa.String(length=36))
    op.create_foreign_key("inventory_movements_product_id_fkey", "inventory_movements", "products", ["product_id"], ["id"])
    op.add_column("inventory_movements", sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=False))

    # --- purchases: id (code) -> code, new UUID id ---
    op.drop_constraint("purchase_lines_purchase_id_fkey", "purchase_lines", type_="foreignkey")
    op.alter_column("purchases", "id", new_column_name="code")
    op.drop_constraint("purchases_pkey", "purchases")
    op.add_column("purchases", sa.Column("id", sa.String(length=36), server_default=sa.text("gen_random_uuid()::text")))
    op.execute("UPDATE purchases SET id = gen_random_uuid()::text WHERE id IS NULL")
    op.alter_column("purchases", "id", nullable=False)
    op.create_primary_key("purchases_pkey", "purchases", ["id"])
    op.add_column("purchases", sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=False))
    op.create_unique_constraint("uq_purchases_company_code", "purchases", ["company_id", "code"])
    op.create_foreign_key("purchases_supplier_id_fkey", "purchases", "suppliers", ["supplier_id"], ["id"])
    op.create_foreign_key("purchase_lines_purchase_id_fkey", "purchase_lines", "purchases", ["purchase_id"], ["id"])
    op.alter_column("purchase_lines", "product_sku", new_column_name="product_id", type_=sa.String(length=36))
    op.create_foreign_key("purchase_lines_product_id_fkey", "purchase_lines", "products", ["product_id"], ["id"])

    # --- sales: id (code) -> code, new UUID id ---
    op.drop_constraint("sale_lines_sale_id_fkey", "sale_lines", type_="foreignkey")
    op.alter_column("sales", "id", new_column_name="code")
    op.drop_constraint("sales_pkey", "sales")
    op.add_column("sales", sa.Column("id", sa.String(length=36), server_default=sa.text("gen_random_uuid()::text")))
    op.execute("UPDATE sales SET id = gen_random_uuid()::text WHERE id IS NULL")
    op.alter_column("sales", "id", nullable=False)
    op.create_primary_key("sales_pkey", "sales", ["id"])
    op.add_column("sales", sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=False))
    op.create_unique_constraint("uq_sales_company_code", "sales", ["company_id", "code"])
    op.create_foreign_key("sales_customer_id_fkey", "sales", "customers", ["customer_id"], ["id"])
    op.create_foreign_key("sale_lines_sale_id_fkey", "sale_lines", "sales", ["sale_id"], ["id"])
    op.alter_column("sale_lines", "product_sku", new_column_name="product_id", type_=sa.String(length=36))
    op.create_foreign_key("sale_lines_product_id_fkey", "sale_lines", "products", ["product_id"], ["id"])

    # --- ledger_entries: add company_id ---
    op.add_column("ledger_entries", sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=False))


def downgrade() -> None:
    raise NotImplementedError("Downgrading the multi-tenant migration is not supported.")
