"""add editable email campaigns and outbox

Revision ID: 202610100001
Revises: 202609280001
"""

import sqlalchemy as sa

from alembic import op

revision = "202610100001"
down_revision = "202609280001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "from_email",
            sa.String(320),
            nullable=False,
            server_default="ceomentality@internet.ru",
        ),
        sa.Column("from_name", sa.String(160), nullable=False, server_default="CEOMENTALITY"),
        sa.Column("sending_key_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "email_campaigns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "drop_id",
            sa.String(160),
            sa.ForeignKey("drops.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_email_campaigns_drop_id", "email_campaigns", ["drop_id"])
    op.create_index("ix_email_campaigns_status", "email_campaigns", ["status"])
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "campaign_id",
            sa.Uuid(),
            sa.ForeignKey("email_campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            sa.String(160),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column("recipient_name", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(150), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_id", sa.String(160), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("campaign_id", "candidate_id", name="uq_email_campaign_candidate"),
    )
    op.create_index("ix_email_outbox_campaign_id", "email_outbox", ["campaign_id"])
    op.create_index("ix_email_outbox_candidate_id", "email_outbox", ["candidate_id"])
    op.create_index("ix_email_outbox_recipient_email", "email_outbox", ["recipient_email"])
    op.create_index("ix_email_outbox_status", "email_outbox", ["status"])
    op.execute(
        """
        INSERT INTO email_settings (id, from_email, from_name)
        VALUES (1, 'ceomentality@internet.ru', 'CEOMENTALITY')
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("email_outbox")
    op.drop_table("email_campaigns")
    op.drop_table("email_settings")
