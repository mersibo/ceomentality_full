export interface ProductPrice { id: string; name: string; unitPrice: number; currency: string; available: boolean; maxQuantity: number }

export type CandidateStatus =
  | 'Under review'
  | 'Approved'
  | 'Rejected'
  | 'Code assigned'
  | 'Code used'
  | 'Accepted'
  | 'Waitlisted'
  | 'Archived';

export type CandidateStage = 'purchase' | 'club';
export type CandidateSource = 'Website' | 'Telegram bot' | 'Partner' | 'Referral' | 'Manual' | 'Import' | 'API';
export type CodeType = 'Single-use' | 'Multi-use';
export type DropStatus = 'Draft' | 'Scheduled' | 'Active' | 'Paused' | 'Closed' | 'Expired' | 'Cancelled';
export type AppRoute = 'Candidate Dossiers' | 'Access Codes' | 'Email' | 'Orders' | 'Analytics' | 'Blacklist' | 'Team' | 'Profile';
export type Language = 'en' | 'ru';

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: 'founder' | 'manager' | 'viewer';
  isActive?: boolean;
  createdAt?: string;
}

export interface Candidate {
  id: string;
  name: string;
  initials: string;
  role: string;
  company: string;
  status: CandidateStatus;
  wave: string;
  code: string | null;
  notes: string[];
  summary: string;
  expertise: string;
  country: string;
  telegram: string;
  source: CandidateSource;
  stage: CandidateStage;
  appliedAt: string;
  telegramId?: string | null;
  deliveryChannel?: 'telegram' | 'email';
  personKey?: string;
  questionnaireAnswers?: Record<string, unknown>;
  socialLinks?: Record<string, unknown>;
  projects?: Array<Record<string, unknown>>;
  achievements?: string[];
  managerComments?: string[];
  decision?: Record<string, unknown>;
  memberProfile?: Record<string, unknown> | null;
  purchaseConfirmed?: boolean;
  purchasedAt?: string | null;
  product?: string;
  addedToGroupsAt?: string | null;
}

export interface AccessBatch {
  id: string;
  name: string;
  description: string;
  issued: number;
  redeemed: number;
  status: DropStatus;
  validity: string;
  code: string;
  codeType?: CodeType;
  source?: CandidateSource;
}

export interface ActivityEvent {
  id: string;
  type: string;
  detail: string;
  at: string;
}

export interface DropIssuePreview {
  dropId: string;
  dropName: string;
  code: string;
  recipients: Array<{ candidateId:string; name:string; telegram:string; deliverable:boolean }>;
  deliverable: number;
  missingTelegram: number;
}

export interface EmailSettings {
  fromEmail: string;
  fromName: string;
  sendingKeyId: number | null;
  providerConfigured: boolean;
}

export interface EmailCampaignPreview {
  dropId: string;
  dropName: string;
  code: string;
  recipients: Array<{ candidateId:string; name:string; email:string|null; deliverable:boolean }>;
  deliverable: number;
  missingEmail: number;
}

export interface EmailCampaign {
  id: string;
  dropId: string;
  dropName: string;
  subject: string;
  body: string;
  status: string;
  recipientCount: number;
  sentCount: number;
  failedCount: number;
  createdAt: string;
  completedAt: string | null;
}

export interface AccessCodeRecord {
  id:string;
  candidateId:string|null;
  value:string;
  status:string;
  validFrom:string|null;
  validUntil:string|null;
  redeemedAt:string|null;
  createdAt:string;
}

export interface NotificationItem {
  id: string;
  type: string;
  detail: string;
  entityType: string | null;
  entityId: string | null;
  isRead: boolean;
  createdAt: string;
}

export interface NotificationState {
  items: NotificationItem[];
  unread: number;
}

export interface CandidateProfile {
  personKey: string;
  applications: Candidate[];
  history: ActivityEvent[];
}

export interface AnalyticsOverview {
  summary: {
    totalApplications: number;
    approved: number;
    rejected: number;
    underReview: number;
    codesAssigned: number;
    codesUsed: number;
    accepted: number;
    purchasesConfirmed: number;
    conversionRate: number;
    purchaseToClubConversion: number;
  };
  timeseries: Array<{ date:string; applications:number; approved:number; codesGenerated:number; codesActivated:number; conversionRate:number }>;
  drops: Array<{ dropId:string; dropName:string; status:DropStatus; validity:string; applications:number; approved:number; rejected:number; codesIssued:number; codesActivated:number; conversionRate:number }>;
}

export interface BlacklistEntry {
  id: string;
  name: string;
  telegramId: string | null;
    telegramUsername: string | null;
    email: string | null;
    phone: string | null;
  reason: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface BlacklistDraft {
  name: string;
  telegramId?: string;
    telegramUsername?: string;
    email?: string;
    phone?: string;
  reason: string;
}

export interface StoreOrder {
  id: string;
  status: string;
  items: Array<{ variantId:string; quantity:number; unitPrice:number }>;
  customer: { name?:string; email?:string; phone?:string; city?:string; address?:string; pickupPointCode?:string; pickupPointName?:string };
  subtotal: number;
  delivery: number;
  total: number;
  currency: string;
  candidateId: string | null;
  createdAt: string;
  payment: { provider:string; providerPaymentId:string; status:string; amount:number } | null;
  tracking: { carrier?:string; number?:string; uuid?:string; status?:string; pickupPointCode?:string; returnPayer?:string } | null;
}

export interface WorkspaceState {
  candidates: Candidate[];
  drops: AccessBatch[];
  activity: ActivityEvent[];
}

export interface WorkspaceFilters {
  status: string;
  wave: string;
  source: string;
  expertise?: string;
  codeType?: string;
  expiry?: string;
  drop?: string;
}

export interface SavedView {
  filters: WorkspaceFilters;
  query: string;
  mode: string;
}

export interface CandidateDraft {
  name: string;
  telegram: string;
  country: string;
  role: string;
  company: string;
  expertise: string;
  wave: string;
  stage: CandidateStage;
  summary: string;
  source: CandidateSource;
}

export interface DropDraft {
  name: string;
  description: string;
  issued: number;
  validity: string;
  code: string;
}

export interface BatchDraft {
  dropId: string;
  codeType: CodeType;
  quantity: number;
  validFrom?: string;
  validUntil?: string;
  prefix?: string;
}
