"""store preferred access-code delivery channel

Revision ID: 202610300001
Revises: 202610290001
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "202610300001"
down_revision: str | None = "202610290001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column(
            "delivery_channel",
            sa.String(length=16),
            nullable=False,
            server_default="telegram",
        ),
    )
    op.create_index(
        op.f("ix_candidates_delivery_channel"),
        "candidates",
        ["delivery_channel"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_candidates_delivery_channel"), table_name="candidates")
    op.drop_column("candidates", "delivery_channel")
