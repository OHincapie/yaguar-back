"""Cartera (accounts receivable): sale_abonos table + Company.credit_days.

- sale_abonos: partial payments registered against a credit sale after the
  fact. Separate from sale_payments on purpose — those describe how the
  sale was arranged at creation and must sum exactly to Sale.total, while
  abonos accumulate over time until they cover it (then the sale flips to
  "pagado" in SaleService.register_abono).
- companies.credit_days: default payment term; a credit sale's due_date is
  its date + this many days unless the caller passes one explicitly.
- Data fixes applied with it: existing 'pendiente' sales got
  due_date = date + 30 days, and customers.saldo was recomputed from real
  open sales (it was dormant seed data before this — nothing wrote it).

Applied directly against Neon; recorded here for history.

Revision ID: 0011_cartera
Revises: 0010_ai_usage_events
Create Date: 2026-07-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_cartera"
down_revision = "0010_ai_usage_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("credit_days", sa.Integer, nullable=False, server_default="30"))
    op.create_table(
        "sale_abonos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sale_id", sa.String(36), sa.ForeignKey("sales.id"), nullable=False),
        sa.Column("payment_method_id", sa.String(36), sa.ForeignKey("payment_methods.id"), nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("notes", sa.String(300), nullable=True),
    )
    op.create_index("ix_sale_abonos_sale_id", "sale_abonos", ["sale_id"])
    op.execute("UPDATE sales SET due_date = date + INTERVAL '30 days' WHERE status = 'pendiente' AND due_date IS NULL")
    op.execute(
        "UPDATE customers SET saldo = COALESCE((SELECT ROUND(SUM(s.total)::numeric, 2) FROM sales s "
        "WHERE s.customer_id = customers.id AND s.status IN ('pendiente', 'vencido')), 0)"
    )


def downgrade() -> None:
    op.drop_index("ix_sale_abonos_sale_id")
    op.drop_table("sale_abonos")
    op.drop_column("companies", "credit_days")
