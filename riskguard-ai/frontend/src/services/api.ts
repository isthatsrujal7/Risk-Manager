const API_BASE = '/api';

export interface CurrentUser { username: string; role: string; display_name?: string }

const TOKEN_KEY = 'riskguard_token';
const USER_KEY = 'riskguard_user';

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

export function setSession(token: string, user: CurrentUser) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch { /* storage unavailable (tests/incognito) */ }
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch { /* noop */ }
}

export function currentUser(): CurrentUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) as CurrentUser : null;
  } catch { return null; }
}

export function hasRole(...roles: string[]): boolean {
  const u = currentUser();
  return !!u && roles.includes(u.role);
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...options?.headers },
    ...options,
  });
  if (res.status === 401 && !url.startsWith('/auth/login')) {
    clearSession();
    if (window.location.pathname !== '/login') window.location.assign('/login');
    throw new Error('Session expired. Please sign in again.');
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API Error ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  health: () => fetchJSON<{ status: string }>('/health'),

  login: (username: string, password: string) =>
    fetchJSON<{ access_token: string; user: CurrentUser }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  me: () => fetchJSON<CurrentUser>('/auth/me'),

  getTransactions: (skip = 0, limit = 50) =>
    fetchJSON<any[]>(`/transactions/?skip=${skip}&limit=${limit}`),

  getTransaction: (id: string) =>
    fetchJSON<any>(`/transactions/${id}`),

  createTransaction: (data: any) =>
    fetchJSON<any>('/transactions/', { method: 'POST', body: JSON.stringify(data) }),

  scoreTransaction: (id: string) =>
    fetchJSON<any>(`/transactions/${id}/score`, { method: 'POST' }),

  getRiskScores: (skip = 0, limit = 50, tier?: string) =>
    fetchJSON<any[]>(`/risk/scores?skip=${skip}&limit=${limit}${tier ? `&tier=${tier}` : ''}`),

  getRiskDistribution: () =>
    fetchJSON<any>('/risk/distribution'),

  getInvestigations: (skip = 0, limit = 50) =>
    fetchJSON<any[]>(`/investigations/?skip=${skip}&limit=${limit}`),

  getInvestigation: (id: string) =>
    fetchJSON<any>(`/investigations/${id}`),

  runInvestigation: (txnId: string) =>
    fetchJSON<any>(`/investigations/${txnId}/investigate`, { method: 'POST' }),

  getReviews: (skip = 0, limit = 50, status?: string) =>
    fetchJSON<any[]>(`/reviews/?skip=${skip}&limit=${limit}${status ? `&status=${status}` : ''}`),

  getPendingReviewCount: () =>
    fetchJSON<{ pending_count: number }>('/reviews/pending-count'),

  submitReview: (data: { investigation_id: string; transaction_id: string; human_decision: string; reviewer_note: string; reviewer_name?: string }) =>
    fetchJSON<any>('/reviews/', { method: 'POST', body: JSON.stringify(data) }),

  getAnalyticsOverview: () =>
    fetchJSON<any>('/analytics/overview'),

  getModelPerformance: () =>
    fetchJSON<any>('/analytics/model-performance'),

  getRiskTrends: () =>
    fetchJSON<any>('/analytics/risk-trends'),

  getAuditTrail: (transactionId?: string, skip = 0, limit = 50) =>
    fetchJSON<any[]>(`/analytics/audit-trail?skip=${skip}&limit=${limit}${transactionId ? `&transaction_id=${transactionId}` : ''}`),

  getFeedbackSummary: () =>
    fetchJSON<any>('/feedback/summary'),

  getErrorPatterns: () =>
    fetchJSON<any>('/feedback/errors'),

  exportFeedback: () =>
    fetchJSON<any>('/feedback/export'),

  recordOutcome: (data: any) =>
    fetchJSON<any>('/feedback/record-outcome', { method: 'POST', body: JSON.stringify(data) }),

  getAuditForTransaction: (txnId: string) =>
    fetchJSON<any[]>(`/audit/${txnId}`),

  getPatternTemplates: () =>
    fetchJSON<any>('/fraud-patterns/templates'),

  detectPatterns: (txnId: string) =>
    fetchJSON<any>(`/fraud-patterns/detect/${txnId}`),

  getPatternsForTransaction: (txnId: string) =>
    fetchJSON<any[]>(`/fraud-patterns/transaction/${txnId}`),

  getPatternSummary: () =>
    fetchJSON<any>('/fraud-patterns/summary'),

  classifyTransaction: (txnId: string) =>
    fetchJSON<any>(`/fraud-patterns/transaction/${txnId}/classify`),

  getHitlSummary: () =>
    fetchJSON<any>('/analytics/hitl-summary'),

  getHitlAlerts: (skip = 0, limit = 50) =>
    fetchJSON<any[]>(`/analytics/hitl-alerts?skip=${skip}&limit=${limit}`),

  detectFraudSpike: (params?: { windowMinutes?: number; baselineHours?: number; zThreshold?: number; minVolume?: number }) =>
    fetchJSON<any>(`/spikes/detect?${new URLSearchParams({
      window_minutes: String(params?.windowMinutes ?? 60),
      baseline_hours: String(params?.baselineHours ?? 168),
      z_threshold: String(params?.zThreshold ?? 3),
      min_volume: String(params?.minVolume ?? 5),
    })}`),

  getSpikeHistory: (limit = 50) =>
    fetchJSON<any[]>(`/spikes/history?limit=${limit}`),

  getSpikeTimeseries: (intervalMinutes = 60, hours = 168) =>
    fetchJSON<any[]>(`/spikes/timeseries?interval_minutes=${intervalMinutes}&hours=${hours}`),

  getMerchants: (tier?: string, limit = 100) =>
    fetchJSON<any[]>(`/merchants/?limit=${limit}${tier ? `&tier=${tier}` : ''}`),

  getMerchant: (merchantId: string) =>
    fetchJSON<any>(`/merchants/${merchantId}`),

  getMerchantSummary: () =>
    fetchJSON<any>('/merchants/summary'),

  rebuildMerchantProfiles: () =>
    fetchJSON<any>('/merchants/rebuild', { method: 'POST' }),

  getLiveRecent: (limit = 20) =>
    fetchJSON<any[]>(`/live/recent?limit=${limit}`),

  getLiveStats: () =>
    fetchJSON<any>('/live/stats'),

  getAlerts: (status?: string, severity?: string, limit = 100) =>
    fetchJSON<any[]>(`/alerts/?limit=${limit}${status ? `&status=${status}` : ''}${severity ? `&severity=${severity}` : ''}`),

  getAlertSummary: () =>
    fetchJSON<any>('/alerts/summary'),

  acknowledgeAlert: (alertId: string, data: { status?: string; assigned_to?: string; resolution_note?: string }) =>
    fetchJSON<any>(`/alerts/${alertId}/acknowledge`, { method: 'POST', body: JSON.stringify(data) }),

  resolveAlert: (alertId: string, data: { assigned_to?: string; resolution_note?: string }) =>
    fetchJSON<any>(`/alerts/${alertId}/resolve`, { method: 'POST', body: JSON.stringify(data) }),

  getFeedbackLoopStatus: () =>
    fetchJSON<any>('/feedback-loop/status'),

  triggerRetrain: () =>
    fetchJSON<any>('/feedback-loop/retrain', { method: 'POST' }),
};

export const liveEventsUrl = () => `${API_BASE}/live/events`;
