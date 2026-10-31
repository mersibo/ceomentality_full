"""add unified candidate identity and admin notifications

Revision ID: 202608080001
Revises: 202608060002
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608080001"
down_revision: str | None = "202608060002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("telegram_outbox", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("candidates", sa.Column("person_key", sa.String(length=200), nullable=True))
    op.add_column("candidates", sa.Column("external_id", sa.String(length=80), nullable=True))
    op.add_column("candidates", sa.Column("purchase_confirmed", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("candidates", sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("candidates", sa.Column("product", sa.String(length=200), server_default="", nullable=False))
    op.add_column("candidates", sa.Column("added_to_groups_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE candidates
        SET person_key = CASE
            WHEN telegram_id IS NOT NULL AND telegram_id <> '' THEN 'tg:' || telegram_id
            WHEN telegram IS NOT NULL AND telegram <> '' THEN 'handle:' || lower(ltrim(telegram, '@'))
            ELSE 'candidate:' || id
        END
        """
    )
    op.alter_column("candidates", "person_key", nullable=False)
    op.create_index(op.f("ix_candidates_person_key"), "candidates", ["person_key"])
    op.create_unique_constraint("uq_candidates_external_id", "candidates", ["external_id"])

    op.create_table(
        "admin_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(length=120), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.String(length=160), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_notifications_user_id"), "admin_notifications", ["user_id"])
    op.create_index(op.f("ix_admin_notifications_type"), "admin_notifications", ["type"])
    op.create_index(op.f("ix_admin_notifications_is_read"), "admin_notifications", ["is_read"])


def downgrade() -> None:
    op.drop_column("telegram_outbox", "last_attempt_at")
    op.drop_table("admin_notifications")
    op.drop_index(op.f("ix_candidates_person_key"), table_name="candidates")
    op.drop_constraint("uq_candidates_external_id", "candidates", type_="unique")
    op.drop_column("candidates", "external_id")
    op.drop_column("candidates", "added_to_groups_at")
    op.drop_column("candidates", "product")
    op.drop_column("candidates", "purchased_at")
    op.drop_column("candidates", "purchase_confirmed")
    op.drop_column("candidates", "person_key")
