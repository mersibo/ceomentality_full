"""allow deferred Telegram delivery by username

Revision ID: 202610290001
Revises: 202610280001
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "202610290001"
down_revision: str | None = "202610280001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("telegram_outbox", "chat_id", existing_type=sa.String(length=80), nullable=True)
    op.add_column(
        "telegram_outbox",
        sa.Column("telegram_username", sa.String(length=120), nullable=True),
    )
    op.create_index(
        op.f("ix_telegram_outbox_telegram_username"),
        "telegram_outbox",
        ["telegram_username"],
        unique=False,
    )


def downgrade() -> None:
    op.execute("DELETE FROM telegram_outbox WHERE chat_id IS NULL")
    op.drop_index(op.f("ix_telegram_outbox_telegram_username"), table_name="telegram_outbox")
    op.drop_column("telegram_outbox", "telegram_username")
    op.alter_column("telegram_outbox", "chat_id", existing_type=sa.String(length=80), nullable=False)
