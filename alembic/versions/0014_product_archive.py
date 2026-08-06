"""Add Product.is_archived (soft delete for products with history).

Deleting a product that already appears in a sale or purchase line would
falsify business history — a received purchase moved stock and wrote a
ledger entry. Such a product is archived instead: hidden from listings,
search, the POS and the chat tools, while the documents referencing it
keep rendering its name and amounts.

Applied directly against Neon; recorded here for history.

Revision ID: 0014_product_archive
Revises: 0013_expense_accounts
Create Date: 2026-08-05
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_product_archive"
down_revision = "0013_expense_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("products", "is_archived")
