"""add public landing, orders and membership invitations

Revision ID: 202609280001
Revises: 202608120001
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "202609280001"
down_revision = "202608120001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("blacklist_entries", sa.Column("email", sa.String(320), nullable=True))
    op.add_column("blacklist_entries", sa.Column("phone", sa.String(32), nullable=True))
    op.create_index("ix_blacklist_entries_email", "blacklist_entries", ["email"])
    op.create_index("ix_blacklist_entries_phone", "blacklist_entries", ["phone"])
    op.create_table(
        "public_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("access_granted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("access_drop_id", sa.String(160), sa.ForeignKey("drops.id"), nullable=True),
        sa.Column("membership_invitation_id", sa.Uuid(), nullable=True),
        sa.Column("membership_candidate_id", sa.String(160), sa.ForeignKey("candidates.id"), nullable=True),
        sa.Column("order_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_public_sessions_token_hash", "public_sessions", ["token_hash"], unique=True)
    op.create_index("ix_public_sessions_expires_at", "public_sessions", ["expires_at"])
    op.create_table(
        "product_variants",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_quantity", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("stock_quantity", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="received"),
        sa.Column("consent", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_contact_messages_email", "contact_messages", ["email"])
    op.create_index("ix_contact_messages_status", "contact_messages", ["status"])
    op.create_table(
        "membership_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("candidate_id", sa.String(160), sa.ForeignKey("candidates.id"), nullable=True),
        sa.Column("order_id", sa.String(100), nullable=True),
        sa.Column("claimed_session_id", sa.Uuid(), sa.ForeignKey("public_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_membership_invitations_token_hash", "membership_invitations", ["token_hash"], unique=True)
    op.create_index("ix_membership_invitations_order_id", "membership_invitations", ["order_id"])
    op.create_index("ix_membership_invitations_expires_at", "membership_invitations", ["expires_at"])
    op.create_table(
        "checkout_quotes",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("public_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("customer", postgresql.JSONB(), nullable=False),
        sa.Column("consents", postgresql.JSONB(), nullable=False),
        sa.Column("subtotal", sa.Integer(), nullable=False),
        sa.Column("delivery", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_checkout_quotes_session_id", "checkout_quotes", ["session_id"])
    op.create_index("ix_checkout_quotes_expires_at", "checkout_quotes", ["expires_at"])
    op.create_table(
        "store_orders",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("public_sessions.id"), nullable=False),
        sa.Column("quote_id", sa.String(100), sa.ForeignKey("checkout_quotes.id"), nullable=False, unique=True),
        sa.Column("candidate_id", sa.String(160), sa.ForeignKey("candidates.id"), nullable=True),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("customer", postgresql.JSONB(), nullable=False),
        sa.Column("consents", postgresql.JSONB(), nullable=False),
        sa.Column("subtotal", sa.Integer(), nullable=False),
        sa.Column("delivery", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("status", sa.String(40), nullable=False, server_default="awaiting_payment"),
        sa.Column("tracking", postgresql.JSONB(), nullable=True),
        sa.Column("claim_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_store_orders_session_id", "store_orders", ["session_id"])
    op.create_index("ix_store_orders_status", "store_orders", ["status"])
    op.create_index("ix_store_orders_claim_token_hash", "store_orders", ["claim_token_hash"], unique=True)
    op.create_table(
        "store_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.String(100), sa.ForeignKey("store_orders.id"), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("provider_payment_id", sa.String(200), nullable=False, unique=True),
        sa.Column("payment_url", sa.Text(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_store_payments_order_id", "store_payments", ["order_id"])
    op.create_index("ix_store_payments_status", "store_payments", ["status"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("public_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation", sa.String(120), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "operation", "key", name="uq_idempotency_scope"),
    )
    op.create_index("ix_idempotency_records_expires_at", "idempotency_records", ["expires_at"])


def downgrade() -> None:
    for table in (
        "idempotency_records", "store_payments", "store_orders", "checkout_quotes",
        "membership_invitations", "contact_messages", "product_variants", "public_sessions",
    ):
        op.drop_table(table)
    op.drop_index("ix_blacklist_entries_phone", table_name="blacklist_entries")
    op.drop_index("ix_blacklist_entries_email", table_name="blacklist_entries")
    op.drop_column("blacklist_entries", "phone")
    op.drop_column("blacklist_entries", "email")
