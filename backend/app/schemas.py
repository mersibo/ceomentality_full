from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import (
    CandidateSource,
    CandidateStage,
    CandidateStatus,
    CodeType,
    DropStatus,
    UserRole,
)


class UserOut(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: UserRole


class UserPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    email: EmailStr | None = None


class AdminUserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.manager


class AdminUserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    email: EmailStr | None = None
    role: UserRole | None = None
    isActive: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class AdminUserOut(UserOut):
    isActive: bool
    createdAt: datetime


class PasswordChangeIn(BaseModel):
    currentPassword: str = Field(min_length=4)
    newPassword: str = Field(min_length=6)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4)


class LoginOut(BaseModel):
    user: UserOut


class SessionOut(BaseModel):
    user: UserOut | None = None


class CandidateOut(BaseModel):
    id: str
    name: str
    initials: str
    role: str
    company: str
    status: CandidateStatus
    wave: str
    code: str | None
    notes: list[str]
    summary: str
    expertise: str
    country: str
    telegram: str
    telegramId: str | None = None
    deliveryChannel: Literal["telegram", "email"] = "telegram"
    personKey: str
    source: CandidateSource
    stage: CandidateStage
    appliedAt: str
    questionnaireAnswers: dict = Field(default_factory=dict)
    socialLinks: dict = Field(default_factory=dict)
    projects: list[dict] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    managerComments: list[str] = Field(default_factory=list)
    decision: dict = Field(default_factory=dict)
    memberProfile: dict | None = None
    purchaseConfirmed: bool = False
    purchasedAt: datetime | None = None
    product: str = ""
    addedToGroupsAt: datetime | None = None


class CandidateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    telegram: str = ""
    deliveryChannel: Literal["telegram", "email"] = "telegram"
    country: str = ""
    role: str = ""
    company: str = ""
    expertise: str = ""
    wave: str = ""
    stage: CandidateStage = CandidateStage.purchase
    summary: str = ""
    source: CandidateSource = CandidateSource.manual
    questionnaireAnswers: dict = Field(default_factory=dict)
    socialLinks: dict = Field(default_factory=dict)
    projects: list[dict] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    managerComments: list[str] = Field(default_factory=list)
    decision: dict = Field(default_factory=dict)
    memberProfile: dict | None = None


class PurchaseApplicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    telegram: str = Field(default="", max_length=120)
    telegramId: str | None = Field(default=None, max_length=80)
    deliveryChannel: Literal["telegram", "email"] = "telegram"
    country: str = Field(default="", max_length=120)
    socialLinks: dict = Field(default_factory=dict)
    role: str = Field(default="", max_length=160)
    company: str = Field(default="", max_length=200)
    expertise: str = Field(default="", max_length=120)
    projects: list[dict] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    summary: str = ""
    source: CandidateSource = CandidateSource.website


class ClubApplicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    telegram: str = Field(default="", max_length=120)
    telegramId: str | None = Field(default=None, max_length=80)
    country: str = Field(default="", max_length=120)
    socialLinks: dict = Field(default_factory=dict)
    activity: str = Field(default="", max_length=120)
    role: str = Field(default="", max_length=160)
    company: str = Field(default="", max_length=200)
    businessInfo: str = ""
    projects: list[dict] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    additionalInfo: str = ""
    questionnaireAnswers: dict = Field(default_factory=dict)
    source: CandidateSource = CandidateSource.telegram_bot


class CandidatePatch(BaseModel):
    name: str | None = None
    telegram: str | None = None
    country: str | None = None
    role: str | None = None
    company: str | None = None
    expertise: str | None = None
    wave: str | None = None
    status: CandidateStatus | None = None
    code: str | None = None
    stage: CandidateStage | None = None
    summary: str | None = None
    source: CandidateSource | None = None
    questionnaireAnswers: dict | None = None
    socialLinks: dict | None = None
    projects: list[dict] | None = None
    achievements: list[str] | None = None
    managerComments: list[str] | None = None
    decision: dict | None = None
    memberProfile: dict | None = None
    purchaseConfirmed: bool | None = None
    purchasedAt: datetime | None = None
    product: str | None = Field(default=None, max_length=200)
    addedToGroupsAt: datetime | None = None


class CandidateDecisionIn(BaseModel):
    status: CandidateStatus
    reason: str = ""
    comment: str | None = None


class PurchaseUpdateIn(BaseModel):
    confirmed: bool = True
    product: str = Field(default="Cardholder", max_length=200)
    purchasedAt: datetime | None = None


class MembershipUpdateIn(BaseModel):
    addedToGroups: bool = True
    addedAt: datetime | None = None


class CandidateNoteCreate(BaseModel):
    text: str = Field(min_length=1)
    visibility: str = "private"


class DropOut(BaseModel):
    id: str
    name: str
    description: str
    issued: int
    redeemed: int
    status: DropStatus
    validity: str
    code: str
    codeType: CodeType | None = None
    source: CandidateSource | None = None


class DropCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    issued: int = Field(default=0, ge=0)
    validity: str = ""
    code: str | None = Field(default=None, max_length=120)


class DropPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    issued: int | None = Field(default=None, ge=0)
    redeemed: int | None = Field(default=None, ge=0)
    status: DropStatus | None = None
    validity: str | None = None
    code: str | None = None
    codeType: CodeType | None = None
    source: CandidateSource | None = None


class DropCodeGenerateIn(BaseModel):
    prefix: str = Field(default="CM", min_length=2, max_length=24)


class DropIssueResult(BaseModel):
    drop: DropOut
    issuedTo: list[str]
    queuedToTelegram: list[str] = Field(default_factory=list)
    skippedTelegram: list[str] = Field(default_factory=list)
    notifications: list[dict] = Field(default_factory=list)


class DropIssueRecipient(BaseModel):
    candidateId: str
    name: str
    telegram: str
    deliverable: bool


class DropIssuePreview(BaseModel):
    dropId: str
    dropName: str
    code: str
    recipients: list[DropIssueRecipient]
    deliverable: int
    missingTelegram: int


class ActivityOut(BaseModel):
    id: str
    type: str
    detail: str
    at: str


class CandidateProfileOut(BaseModel):
    personKey: str
    applications: list[CandidateOut]
    history: list[ActivityOut]


class NotificationOut(BaseModel):
    id: UUID
    type: str
    detail: str
    entityType: str | None = None
    entityId: str | None = None
    isRead: bool
    createdAt: datetime


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread: int


class WorkspaceState(BaseModel):
    candidates: list[CandidateOut]
    drops: list[DropOut]
    activity: list[ActivityOut]


class WorkspaceSearchOut(BaseModel):
    candidates: list[CandidateOut]
    drops: list[DropOut]
    codes: list[str] = []


class CodeBatchCreate(BaseModel):
    dropId: str
    codeType: CodeType = CodeType.single_use
    quantity: int = Field(ge=1, le=10_000)
    validFrom: datetime | None = None
    validUntil: datetime | None = None
    prefix: str = Field(default="CM", min_length=2, max_length=24)


class CodeBatchOut(BaseModel):
    id: UUID
    dropId: str
    codeType: CodeType
    issued: int
    redeemed: int
    status: DropStatus


class RedeemCodeIn(BaseModel):
    code: str = Field(min_length=3, max_length=120)
    candidateId: str | None = None


class RedeemCodeOut(BaseModel):
    success: bool
    code: dict


class TelegramUserUpsertIn(BaseModel):
    telegramId: int
    username: str | None = Field(default=None, max_length=120)
    firstName: str | None = Field(default=None, max_length=160)
    lastName: str | None = Field(default=None, max_length=160)
    languageCode: str | None = Field(default=None, max_length=16)
    isBot: bool = False


class TelegramUserOut(BaseModel):
    telegramId: int
    username: str | None = None
    firstName: str | None = None
    lastName: str | None = None


class TelegramApplicationIn(BaseModel):
    submissionId: str = Field(min_length=8, max_length=80)
    telegramId: int
    username: str | None = Field(default=None, max_length=120)
    firstName: str | None = Field(default=None, max_length=160)
    lastName: str | None = Field(default=None, max_length=160)
    text: str = Field(min_length=1)
    applicationType: CandidateStage = CandidateStage.purchase
    source: CandidateSource = CandidateSource.telegram_bot
    raw: dict = Field(default_factory=dict)


class BlacklistEntryCreate(BaseModel):
    name: str = Field(default="", max_length=200)
    telegramId: str | None = Field(default=None, max_length=80)
    telegramUsername: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    reason: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def require_identifier(self) -> "BlacklistEntryCreate":
        if not any((self.telegramId, self.telegramUsername, self.email, self.phone)):
            raise ValueError("at least one identifier is required")
        return self


class BlacklistEntryPatch(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    telegramId: str | None = Field(default=None, max_length=80)
    telegramUsername: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    reason: str | None = Field(default=None, min_length=1, max_length=4000)
    isActive: bool | None = None


class BlacklistEntryOut(BaseModel):
    id: UUID
    name: str
    telegramId: str | None = None
    telegramUsername: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    reason: str
    isActive: bool
    createdAt: datetime
    updatedAt: datetime


class StorePaymentAdminOut(BaseModel):
    provider: str
    providerPaymentId: str
    status: str
    amount: int


class StoreOrderAdminOut(BaseModel):
    id: str
    status: str
    items: list[dict]
    customer: dict
    subtotal: int
    delivery: int
    total: int
    currency: str
    candidateId: str | None
    createdAt: datetime
    payment: StorePaymentAdminOut | None = None
    tracking: dict | None = None


class TelegramBlacklistCheckIn(BaseModel):
    telegramId: int
    username: str | None = Field(default=None, max_length=120)


class TelegramBlacklistCheckOut(BaseModel):
    blocked: bool
    reason: str | None = None
    message: str | None = None


class TelegramOutboxMessageOut(BaseModel):
    id: UUID
    chatId: str
    text: str
    entityType: str | None = None
    entityId: str | None = None
    attempts: int
    createdAt: datetime


class TelegramOutboxAckIn(BaseModel):
    status: Literal["sent", "failed"]
    error: str | None = Field(default=None, max_length=4000)


class EmailSettingsOut(BaseModel):
    fromEmail: EmailStr
    fromName: str
    sendingKeyId: int | None = None
    providerConfigured: bool


class EmailSettingsPatch(BaseModel):
    fromEmail: EmailStr
    fromName: str = Field(min_length=1, max_length=160)
    sendingKeyId: int | None = Field(default=None, ge=1)


class EmailRecipientOut(BaseModel):
    candidateId: str
    name: str
    email: EmailStr | None = None
    deliverable: bool


class EmailCampaignPreviewIn(BaseModel):
    dropId: str = Field(min_length=1, max_length=160)


class EmailCampaignPreviewOut(BaseModel):
    dropId: str
    dropName: str
    code: str
    recipients: list[EmailRecipientOut]
    deliverable: int
    missingEmail: int


class EmailCampaignCreate(BaseModel):
    dropId: str = Field(min_length=1, max_length=160)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=20000)


class EmailCampaignOut(BaseModel):
    id: UUID
    dropId: str
    dropName: str
    subject: str
    body: str
    status: str
    recipientCount: int
    sentCount: int
    failedCount: int
    createdAt: datetime
    completedAt: datetime | None = None


class AccessCodeOut(BaseModel):
    id: UUID
    candidateId: str | None = None
    value: str
    status: str
    validFrom: datetime | None = None
    validUntil: datetime | None = None
    redeemedAt: datetime | None = None
    createdAt: datetime


class PaginatedCandidates(BaseModel):
    items: list[CandidateOut]
    pagination: dict[str, int]


class MessageOut(BaseModel):
    message: str


class AnalyticsSummaryOut(BaseModel):
    totalApplications: int
    approved: int
    rejected: int
    underReview: int
    codesAssigned: int
    codesUsed: int
    conversionRate: float


class AnalyticsDropOut(BaseModel):
    dropId: str
    dropName: str
    applications: int
    approved: int
    rejected: int
    codesIssued: int
    usersWithAccess: int


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
