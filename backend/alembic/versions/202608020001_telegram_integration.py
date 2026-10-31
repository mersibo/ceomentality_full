"""add telegram integration users

Revision ID: 202608020001
Revises: 202607150100
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608020001"
down_revision: str | None = "202607150100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=True),
        sa.Column("first_name", sa.String(length=160), nullable=True),
        sa.Column("last_name", sa.String(length=160), nullable=True),
        sa.Column("language_code", sa.String(length=16), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_telegram_users_telegram_id"), "telegram_users", ["telegram_id"], unique=True)
    op.create_index(op.f("ix_telegram_users_username"), "telegram_users", ["username"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_telegram_users_username"), table_name="telegram_users")
    op.drop_index(op.f("ix_telegram_users_telegram_id"), table_name="telegram_users")
    op.drop_table("telegram_users")
