"""add blacklist and external telegram outbox

Revision ID: 202608060001
Revises: 202608020001
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608060001"
down_revision: str | None = "202608020001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "blacklist_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("telegram_id", sa.String(length=80), nullable=True),
        sa.Column("telegram_username", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_blacklist_entries_is_active"), "blacklist_entries", ["is_active"])
    op.create_index(op.f("ix_blacklist_entries_telegram_id"), "blacklist_entries", ["telegram_id"])
    op.create_index(
        op.f("ix_blacklist_entries_telegram_username"),
        "blacklist_entries",
        ["telegram_username"],
    )

    op.create_table(
        "telegram_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chat_id", sa.String(length=80), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_telegram_outbox_chat_id"), "telegram_outbox", ["chat_id"])
    op.create_index(op.f("ix_telegram_outbox_status"), "telegram_outbox", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_telegram_outbox_status"), table_name="telegram_outbox")
    op.drop_index(op.f("ix_telegram_outbox_chat_id"), table_name="telegram_outbox")
    op.drop_table("telegram_outbox")
    op.drop_index(op.f("ix_blacklist_entries_telegram_username"), table_name="blacklist_entries")
    op.drop_index(op.f("ix_blacklist_entries_telegram_id"), table_name="blacklist_entries")
    op.drop_index(op.f("ix_blacklist_entries_is_active"), table_name="blacklist_entries")
    op.drop_table("blacklist_entries")
