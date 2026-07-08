"""Configurable payment methods + split payments per sale.

Replaces the hardcoded PaymentMethod enum (Efectivo/Tarjeta/Transferencia/
Crédito) with a company-configurable `payment_methods` table, and adds
`sale_payments` so a sale can be paid across several methods at once (e.g.
part cash, part transfer) instead of a single payment_method field.
Sale.customer_id turned out to already be nullable in the live DB despite
the old model saying otherwise — no ALTER needed there; a null customer_id
now means a walk-in/casual sale.

Existing sales were backfilled with one sale_payments row each (amount =
sale.total, method resolved by name) so nothing changes for sales created
before this migration. Applied directly against Neon; recorded here for
history.

Revision ID: 0008_split_payments
Revises: 0007_user_modules
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_split_payments"
down_revision = "0007_user_modules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("is_credit", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("company_id", "name", name="uq_payment_methods_company_name"),
    )
    op.create_index("ix_payment_methods_company_id", "payment_methods", ["company_id"])

    op.create_table(
        "sale_payments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sale_id", sa.String(36), sa.ForeignKey("sales.id"), nullable=False),
        sa.Column("payment_method_id", sa.String(36), sa.ForeignKey("payment_methods.id"), nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
    )

    # Seed the 4 default methods per existing company + backfill one
    # sale_payments row per existing sale (see docstring above) — done via
    # raw SQL against Neon at apply time, not repeated here since Alembic
    # migrations in this project are written for history, not re-run.


def downgrade() -> None:
    op.drop_table("sale_payments")
    op.drop_index("ix_payment_methods_company_id", table_name="payment_methods")
    op.drop_table("payment_methods")
