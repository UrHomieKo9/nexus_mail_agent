/**
 * API Client — communicates with the FastAPI backend.
 */

const API_BASE = "/api/v1";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });

  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(error.detail || `API error: ${resp.status}`);
  }

  return resp.json();
}

// ── Auth ──

export function connectProvider(provider: string, redirectUri: string) {
  return request<{ authorization_url: string }>("/auth/connect", {
    method: "POST",
    body: JSON.stringify({ provider, redirect_uri: redirectUri }),
  });
}

// ── Emails ──

export function fetchEmails(userId: string, provider: string, maxResults = 50) {
  return request<{ status: string; task_id: string }>("/emails/fetch", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, provider, max_results: maxResults }),
  });
}

export function getStats(userId: string) {
  return request<{
    user_id: string;
    emails: number;
    drafts: number;
    leads: number;
    campaigns: number;
  }>(`/stats/${userId}`);
}

/** Run the analyst/copywriter/critic pipeline on stored emails (async on server). */
export function processStoredPipeline(userId: string, maxEmails = 30) {
  return request<{
    status: string;
    user_id: string;
    emails_considered: number;
    drafts_created: number;
    skipped: number;
    pipeline_errors: number;
  }>(`/emails/${userId}/process-pipeline?max_emails=${maxEmails}`, {
    method: "POST",
  });
}

export function listEmails(userId: string, page = 1, pageSize = 20) {
  return request<{ items: any[]; page: number; has_next: boolean }>(
    `/emails/${userId}?page=${page}&page_size=${pageSize}`
  );
}

export function getThread(userId: string, threadId: string) {
  return request<{ thread_id: string; messages: any[] }>(
    `/emails/${userId}/thread/${threadId}`
  );
}

// ── Drafts ──

export function listDrafts(userId: string, status?: string, page = 1) {
  let url = `/drafts/${userId}?page=${page}`;
  if (status) url += `&status=${status}`;
  return request<{ items: any[] }>(url);
}

export function reviewDraft(draftId: string, action: string, editedBody?: string) {
  return request<{ status: string }>(`/drafts/${draftId}/review`, {
    method: "POST",
    body: JSON.stringify({ action, edited_body: editedBody }),
  });
}

export function sendDraft(draftId: string, applyJitter = true) {
  return request<{ status: string; task_id: string }>(`/drafts/${draftId}/send`, {
    method: "POST",
    body: JSON.stringify({ draft_id: draftId, apply_jitter: applyJitter }),
  });
}

// ── Leads ──

export function listLeads(userId: string, page = 1) {
  return request<{ items: any[] }>(`/leads/${userId}?page=${page}`);
}

export function enrichLead(email: string) {
  return request<any>(`/leads/enrich?email=${encodeURIComponent(email)}`, {
    method: "POST",
  });
}

// ── Campaigns ──

export function listCampaigns(userId: string) {
  return request<{ campaigns: any[] }>(`/campaigns/${userId}`);
}

export function createCampaign(data: {
  user_id: string;
  name: string;
  subject_template: string;
  body_template: string;
  recipient_emails: string[];
}) {
  return request<{ campaign_id: string }>("/campaigns", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function startCampaign(campaignId: string, applyJitter = true) {
  return request<{ status: string }>("/campaigns/start", {
    method: "POST",
    body: JSON.stringify({ campaign_id: campaignId, apply_jitter: applyJitter }),
  });
}

export function pauseCampaign(campaignId: string) {
  return request<{ status: string }>(`/campaigns/${campaignId}/pause`, {
    method: "POST",
  });
}
