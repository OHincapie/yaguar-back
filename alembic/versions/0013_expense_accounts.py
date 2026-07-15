"""Expense accounts (Gastos module) + ledger_entries.account_id.

A company-configurable, flat list of operational-expense accounts (name +
optional PUC code + color), seeded per company with the common Colombian
grupo-51 accounts. Manual expenses are ledger OUT entries tagged with an
account_id pointing here — so they flow into Egresos / Balance / the
dashboard cashflow like everything else, but carry their own account +
color. This is the pragmatic middle ground toward the future full-PUC /
double-entry vision (see backlog).

Applied directly against Neon; recorded here for history.

Revision ID: 0013_expense_accounts
Revises: 0012_margin_basis
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_expense_accounts"
down_revision = "0012_margin_basis"
branch_labels = None
depends_on = None

DEFAULTS = [
    ("Gastos de personal", "5105", "#EF4444"),
    ("Honorarios", "5110", "#F59E0B"),
    ("Impuestos", "5115", "#8B5CF6"),
    ("Arrendamientos", "5120", "#3B82F6"),
    ("Servicios", "5135", "#10B981"),
    ("Mantenimiento y reparaciones", "5145", "#14B8A6"),
    ("Gastos de viaje", "5155", "#F97316"),
    ("Diversos", "5195", "#6366F1"),
]


def upgrade() -> None:
    op.create_table(
        "expense_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("puc_code", sa.String(20), nullable=True),
        sa.Column("color", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("company_id", "name", name="uq_expense_accounts_company_name"),
    )
    op.create_index("ix_expense_accounts_company_id", "expense_accounts", ["company_id"])
    op.add_column("ledger_entries", sa.Column("account_id", sa.String(36), sa.ForeignKey("expense_accounts.id"), nullable=True))
    # Seed the default accounts for every existing company.
    values = ", ".join(
        f"('{name}','{code}','{color}')" for name, code, color in DEFAULTS
    )
    op.execute(
        "INSERT INTO expense_accounts (id, company_id, name, puc_code, color) "
        "SELECT gen_random_uuid()::text, c.id, v.name, v.code, v.color "
        f"FROM companies c CROSS JOIN (VALUES {values}) AS v(name, code, color)"
    )


def downgrade() -> None:
    op.drop_column("ledger_entries", "account_id")
    op.drop_index("ix_expense_accounts_company_id")
    op.drop_table("expense_accounts")
