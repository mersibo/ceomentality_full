"""Unique per-candidate drop access codes.

Revision ID: 202610280001
Revises: 202610100001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202610280001"
down_revision: str | None = "202610100001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("access_codes", sa.Column("drop_id", sa.String(length=160), nullable=True))
    op.create_foreign_key(
        "fk_access_codes_drop_id", "access_codes", "drops", ["drop_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_access_codes_drop_id", "access_codes", ["drop_id"])
    op.execute(
        """
        UPDATE access_codes
        SET status = 'Expired'
        WHERE status = 'Active' AND candidate_id IS NOT NULL AND drop_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE candidates AS candidate
        SET code = NULL, status = 'Approved'
        WHERE candidate.status = 'Code assigned'
          AND (
            EXISTS (
              SELECT 1 FROM access_codes AS code
              WHERE code.candidate_id = candidate.id
                AND code.drop_id IS NULL
                AND code.status = 'Expired'
            )
            OR EXISTS (
              SELECT 1 FROM drops AS drop
              WHERE drop.name = candidate.wave AND drop.code = candidate.code
            )
          )
        """
    )
    op.create_index(
        "uq_access_codes_active_value",
        "access_codes",
        ["value"],
        unique=True,
        postgresql_where=sa.text("status = 'Active'"),
    )
    op.create_index(
        "uq_access_codes_active_drop_candidate",
        "access_codes",
        ["drop_id", "candidate_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('Active', 'Redeemed') AND drop_id IS NOT NULL AND candidate_id IS NOT NULL"),
    )
    op.add_column("public_sessions", sa.Column("access_code_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_public_sessions_access_code_id",
        "public_sessions",
        "access_codes",
        ["access_code_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_public_sessions_access_code_id", "public_sessions", type_="foreignkey")
    op.drop_column("public_sessions", "access_code_id")
    op.drop_index("uq_access_codes_active_value", table_name="access_codes")
    op.drop_index("uq_access_codes_active_drop_candidate", table_name="access_codes")
    op.drop_index("ix_access_codes_drop_id", table_name="access_codes")
    op.drop_constraint("fk_access_codes_drop_id", "access_codes", type_="foreignkey")
    op.drop_column("access_codes", "drop_id")
