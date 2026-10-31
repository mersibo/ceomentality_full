import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TextEnum(str, enum.Enum):
    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


class UserRole(TextEnum):
    founder = "founder"
    manager = "manager"
    viewer = "viewer"


class CandidateStatus(TextEnum):
    under_review = "Under review"
    approved = "Approved"
    rejected = "Rejected"
    code_assigned = "Code assigned"
    code_used = "Code used"
    accepted = "Accepted"
    waitlisted = "Waitlisted"
    archived = "Archived"


class CandidateStage(TextEnum):
    purchase = "purchase"
    club = "club"


class CandidateSource(TextEnum):
    website = "Website"
    telegram_bot = "Telegram bot"
    partner = "Partner"
    referral = "Referral"
    manual = "Manual"
    import_ = "Import"
    api = "API"


class DropStatus(TextEnum):
    draft = "Draft"
    scheduled = "Scheduled"
    active = "Active"
    paused = "Paused"
    closed = "Closed"
    expired = "Expired"
    cancelled = "Cancelled"


class CodeType(TextEnum):
    single_use = "Single-use"
    multi_use = "Multi-use"


class AccessCodeStatus(TextEnum):
    active = "Active"
    redeemed = "Redeemed"
    expired = "Expired"
    revoked = "Revoked"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.manager.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    initials: Mapped[str] = mapped_column(String(8))
    role: Mapped[str] = mapped_column(String(160), default="")
    company: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(40), default=CandidateStatus.under_review.value)
    wave: Mapped[str] = mapped_column(String(80), default="")
    code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    expertise: Mapped[str] = mapped_column(String(120), default="")
    country: Mapped[str] = mapped_column(String(120), default="")
    telegram: Mapped[str] = mapped_column(String(120), default="")
    telegram_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    delivery_channel: Mapped[str] = mapped_column(String(16), default="telegram", index=True)
    person_key: Mapped[str] = mapped_column(String(200), index=True)
    external_id: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    questionnaire_answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    social_links: Mapped[dict] = mapped_column(JSONB, default=dict)
    projects: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    achievements: Mapped[list[str]] = mapped_column(JSONB, default=list)
    manager_comments: Mapped[list[str]] = mapped_column(JSONB, default=list)
    decision: Mapped[dict] = mapped_column(JSONB, default=dict)
    member_profile: Mapped[dict | None] = mapped_column(JSONB, default=None, nullable=True)
    purchase_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    product: Mapped[str] = mapped_column(String(200), default="")
    added_to_groups_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default=CandidateSource.manual.value)
    stage: Mapped[str] = mapped_column(String(40), default=CandidateStage.purchase.value)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    notes: Mapped[list["CandidateNote"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )


class CandidateNote(Base):
    __tablename__ = "candidate_notes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(40), default="private")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    candidate: Mapped[Candidate] = relationship(back_populates="notes")


class Drop(Base):
    __tablename__ = "drops"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    issued: Mapped[int] = mapped_column(Integer, default=0)
    redeemed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default=DropStatus.draft.value)
    validity: Mapped[str] = mapped_column(String(160), default="")
    code: Mapped[str] = mapped_column(String(120), unique=True)
    code_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    batches: Mapped[list["CodeBatch"]] = relationship(back_populates="drop", lazy="selectin")


class CodeBatch(Base):
    __tablename__ = "code_batches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    drop_id: Mapped[str] = mapped_column(ForeignKey("drops.id", ondelete="CASCADE"))
    code_type: Mapped[str] = mapped_column(String(40), default=CodeType.single_use.value)
    issued: Mapped[int] = mapped_column(Integer, default=0)
    redeemed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default=DropStatus.active.value)
    prefix: Mapped[str] = mapped_column(String(40), default="CM")
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    drop: Mapped[Drop] = relationship(back_populates="batches")


class AccessCode(Base):
    __tablename__ = "access_codes"
    __table_args__ = (UniqueConstraint("candidate_id", "value", name="uq_access_codes_candidate_value"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("code_batches.id"), nullable=True)
    drop_id: Mapped[str | None] = mapped_column(ForeignKey("drops.id", ondelete="CASCADE"), nullable=True, index=True)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"), nullable=True)
    value: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(40), default=AccessCodeStatus.active.value)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BlacklistEntry(Base):
    __tablename__ = "blacklist_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), default="")
    telegram_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TelegramOutboxMessage(Base):
    __tablename__ = "telegram_outbox"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chat_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailSettings(Base):
    __tablename__ = "email_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    from_email: Mapped[str] = mapped_column(String(320), default="ceomentality@internet.ru")
    from_name: Mapped[str] = mapped_column(String(160), default="CEOMENTALITY")
    sending_key_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmailCampaign(Base):
    __tablename__ = "email_campaigns"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    drop_id: Mapped[str] = mapped_column(ForeignKey("drops.id", ondelete="CASCADE"), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    recipient_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailOutboxMessage(Base):
    __tablename__ = "email_outbox"
    __table_args__ = (
        UniqueConstraint("campaign_id", "candidate_id", name="uq_email_campaign_candidate"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_campaigns.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    recipient_email: Mapped[str] = mapped_column(String(320), index=True)
    recipient_name: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(150), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    provider_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(String(120), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminNotification(Base):
    __tablename__ = "admin_notifications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(120), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PublicSession(Base):
    __tablename__ = "public_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    access_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    access_drop_id: Mapped[str | None] = mapped_column(ForeignKey("drops.id"), nullable=True)
    access_code_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("access_codes.id", ondelete="SET NULL"), nullable=True
    )
    membership_invitation_id: Mapped[UUID | None] = mapped_column(nullable=True)
    membership_candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("candidates.id"), nullable=True
    )
    order_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    unit_price: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    max_quantity: Mapped[int] = mapped_column(Integer, default=10)
    stock_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(300))
    email: Mapped[str] = mapped_column(String(320), index=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="received", index=True)
    consent: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MembershipInvitation(Base):
    __tablename__ = "membership_invitations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    claimed_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("public_sessions.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CheckoutQuote(Base):
    __tablename__ = "checkout_quotes"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("public_sessions.id", ondelete="CASCADE"), index=True)
    items: Mapped[list[dict]] = mapped_column(JSONB)
    customer: Mapped[dict] = mapped_column(JSONB)
    consents: Mapped[dict] = mapped_column(JSONB)
    subtotal: Mapped[int] = mapped_column(Integer)
    delivery: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    payload_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StoreOrder(Base):
    __tablename__ = "store_orders"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("public_sessions.id"), index=True)
    quote_id: Mapped[str] = mapped_column(ForeignKey("checkout_quotes.id"), unique=True)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"), nullable=True)
    items: Mapped[list[dict]] = mapped_column(JSONB)
    customer: Mapped[dict] = mapped_column(JSONB)
    consents: Mapped[dict] = mapped_column(JSONB)
    subtotal: Mapped[int] = mapped_column(Integer)
    delivery: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[str] = mapped_column(String(40), default="awaiting_payment", index=True)
    tracking: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    claim_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StorePayment(Base):
    __tablename__ = "store_payments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[str] = mapped_column(ForeignKey("store_orders.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    provider_payment_id: Mapped[str] = mapped_column(String(200), unique=True)
    payment_url: Mapped[str] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("session_id", "operation", "key", name="uq_idempotency_scope"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("public_sessions.id", ondelete="CASCADE"))
    operation: Mapped[str] = mapped_column(String(120))
    key: Mapped[str] = mapped_column(String(120))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
