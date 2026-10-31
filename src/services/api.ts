import type {
  AccessBatch,
  AccessCodeRecord,
  AdminUser,
  AnalyticsOverview,
  BatchDraft,
  BlacklistDraft,
  BlacklistEntry,
  Candidate,
  CandidateDraft,
  CandidateProfile,
  CandidateStatus,
  DropDraft,
  DropIssuePreview,
  EmailCampaign,
  EmailCampaignPreview,
  EmailSettings,
  NotificationState,
  StoreOrder,
  ProductPrice,
  WorkspaceState,
} from '../types/domain';

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    const detail = error?.detail;
    throw new Error(error?.error?.message ?? detail?.message ?? detail ?? `Request failed with status ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  load: (): Promise<WorkspaceState> => request('/api/workspace'),
  save: (state: WorkspaceState): Promise<WorkspaceState> => request('/api/workspace', { method: 'PUT', body: JSON.stringify(state) }),
  search: (query: string) => request<{ candidates: Candidate[]; drops: AccessBatch[]; codes: string[] }>(`/api/search?q=${encodeURIComponent(query)}`),
  reset: (): Promise<WorkspaceState> => request('/api/workspace/reset', { method: 'POST' }),
  login: (credentials: { email: string; password: string }): Promise<{ user: AdminUser }> => request('/api/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: (): Promise<{ user: AdminUser }> => request('/api/auth/me'),
  session: (): Promise<{ user: AdminUser | null }> => request('/api/auth/session'),
  updateMe: (profile: Partial<AdminUser>): Promise<{ user: AdminUser }> => request('/api/auth/me', { method: 'PATCH', body: JSON.stringify({ name: profile.name, email: profile.email }) }),
  changePassword: (payload: { currentPassword: string; newPassword: string }): Promise<{ message: string }> => request('/api/auth/me/password', { method: 'POST', body: JSON.stringify(payload) }),
  export: (state: WorkspaceState) => new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' }),
  createCandidate: (draft: CandidateDraft): Promise<Candidate> => request('/api/candidates', { method: 'POST', body: JSON.stringify(draft) }),
  updateCandidate: (id: string, patch: Partial<Candidate>): Promise<Candidate> => request(`/api/candidates/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  decideCandidate: (id: string, payload: { status: CandidateStatus; reason?: string; comment?: string }): Promise<Candidate> => request(`/api/candidates/${id}/decision`, { method: 'POST', body: JSON.stringify(payload) }),
  addCandidateNote: (id: string, text: string): Promise<Candidate> => request(`/api/candidates/${id}/notes`, { method: 'POST', body: JSON.stringify({ text }) }),
  createDrop: (draft: DropDraft): Promise<AccessBatch> => request('/api/drops', { method: 'POST', body: JSON.stringify(draft) }),
  createCodeBatch: (draft: BatchDraft): Promise<{ id: string; dropId: string; codeType: string; issued: number; redeemed: number; status: string }> => request('/api/code-batches', { method: 'POST', body: JSON.stringify(draft) }),
  listAccessCodes: (): Promise<AccessCodeRecord[]> => request('/api/access-codes'),
  updateDrop: (id: string, patch: Partial<AccessBatch>): Promise<AccessBatch> => request(`/api/drops/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  activateDrop: (id: string): Promise<AccessBatch> => request(`/api/drops/${id}/activate`, { method: 'POST' }),
  generateDropCode: (id: string, prefix = 'CM'): Promise<AccessBatch> => request(`/api/drops/${id}/generate-code`, { method: 'POST', body: JSON.stringify({ prefix }) }),
  issueDropCodeToApproved: (id: string): Promise<{ drop: AccessBatch; issuedTo: string[]; queuedToTelegram: string[]; skippedTelegram: string[]; notifications: unknown[] }> => request(`/api/drops/${id}/issue-code-to-approved`, { method: 'POST' }),
  previewDropCodeRecipients: (id: string): Promise<DropIssuePreview> => request(`/api/drops/${id}/issue-preview`),
  closeDrop: (id: string): Promise<AccessBatch> => request(`/api/drops/${id}/close`, { method: 'POST' }),
  deleteDrop: (id: string): Promise<void> => request(`/api/drops/${id}`, { method: 'DELETE' }),
  emailSettings: (): Promise<EmailSettings> => request('/api/email/settings'),
  updateEmailSettings: (payload: Omit<EmailSettings,'providerConfigured'>): Promise<EmailSettings> => request('/api/email/settings', { method: 'PATCH', body: JSON.stringify(payload) }),
  previewEmailCampaign: (dropId:string): Promise<EmailCampaignPreview> => request('/api/email/campaigns/preview', { method: 'POST', body: JSON.stringify({dropId}) }),
  listEmailCampaigns: (): Promise<EmailCampaign[]> => request('/api/email/campaigns'),
  createEmailCampaign: (payload:{dropId:string;subject:string;body:string}): Promise<EmailCampaign> => request('/api/email/campaigns', { method: 'POST', body: JSON.stringify(payload) }),
  assignCandidateCode: (id: string): Promise<unknown> => request(`/api/candidates/${id}/access-code`, { method: 'POST' }),
  listBlacklist: (): Promise<BlacklistEntry[]> => request('/api/blacklist'),
  addBlacklistEntry: (draft: BlacklistDraft): Promise<BlacklistEntry> => request('/api/blacklist', { method: 'POST', body: JSON.stringify(draft) }),
  removeBlacklistEntry: (id: string): Promise<{ message: string }> => request(`/api/blacklist/${id}`, { method: 'DELETE' }),
  getCandidateProfile: (id: string): Promise<CandidateProfile> => request(`/api/candidates/${id}/profile`),
  updatePurchase: (id: string, payload: { confirmed: boolean; product: string }): Promise<Candidate> => request(`/api/candidates/${id}/purchase`, { method: 'POST', body: JSON.stringify(payload) }),
  updateMembership: (id: string, payload: { addedToGroups: boolean }): Promise<Candidate> => request(`/api/candidates/${id}/membership`, { method: 'POST', body: JSON.stringify(payload) }),
  getAnalytics: (params: string): Promise<AnalyticsOverview> => request(`/api/analytics/overview${params ? `?${params}` : ''}`),
  notifications: (): Promise<NotificationState> => request('/api/notifications'),
  readNotification: (id: string) => request(`/api/notifications/${id}/read`, { method: 'PATCH' }),
  readAllNotifications: () => request('/api/notifications/read-all', { method: 'POST' }),
  listUsers: (): Promise<AdminUser[]> => request('/api/users'),
  listOrders: (): Promise<StoreOrder[]> => request('/api/orders'),
  listProducts: (): Promise<ProductPrice[]> => request('/api/products'),
  updateProductPrice: (id: string, unitPrice: number): Promise<ProductPrice> => request(`/api/products/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ unitPrice }) }),
  deleteOrder: (id: string): Promise<void> => request(`/api/orders/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  refundOrder: (id: string): Promise<StoreOrder> => request(`/api/orders/${encodeURIComponent(id)}/refund`, { method: 'POST' }),
  completeOrder: (id: string): Promise<StoreOrder> => request(`/api/orders/${encodeURIComponent(id)}/complete`, { method: 'POST' }),
  createShipment: (id: string): Promise<StoreOrder> => request(`/api/orders/${encodeURIComponent(id)}/shipment`, { method: 'POST' }),
  refreshShipment: (id: string): Promise<StoreOrder> => request(`/api/orders/${encodeURIComponent(id)}/shipment/refresh`, { method: 'POST' }),
  createUser: (payload: { name: string; email: string; password: string; role: AdminUser['role'] }): Promise<AdminUser> => request('/api/users', { method: 'POST', body: JSON.stringify(payload) }),
  updateUser: (id: string, payload: Partial<AdminUser> & { password?: string }): Promise<AdminUser> => request(`/api/users/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deactivateUser: (id: string): Promise<{ message:string }> => request(`/api/users/${id}`, { method: 'DELETE' }),
};
