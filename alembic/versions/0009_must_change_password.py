"""Add User.must_change_password.

Set True whenever an admin (not the user themselves) chooses a user's
password — creating a new user via /auth/users, or resetting an existing
one's password. Cleared by the new POST /auth/change-password once the
user sets their own. Registering your own company (POST /auth/register)
leaves it False since you picked your own password there.

Applied directly against Neon; recorded here for history.

Revision ID: 0009_must_change_password
Revises: 0008_split_payments
Create Date: 2026-07-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_must_change_password"
down_revision = "0008_split_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
