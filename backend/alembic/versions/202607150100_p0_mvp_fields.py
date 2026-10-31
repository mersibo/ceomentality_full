"""add p0 candidate profile and history fields

Revision ID: 202607150100
Revises: 202607150001
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607150100"
down_revision: str | None = "202607150001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("questionnaire_answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("candidates", sa.Column("social_links", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("candidates", sa.Column("projects", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("candidates", sa.Column("achievements", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("candidates", sa.Column("manager_comments", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("candidates", sa.Column("decision", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("candidates", sa.Column("member_profile", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "member_profile")
    op.drop_column("candidates", "decision")
    op.drop_column("candidates", "manager_comments")
    op.drop_column("candidates", "achievements")
    op.drop_column("candidates", "projects")
    op.drop_column("candidates", "social_links")
    op.drop_column("candidates", "questionnaire_answers")
