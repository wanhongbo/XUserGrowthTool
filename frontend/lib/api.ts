export type Score = {
  relevance: number;
  activity: number;
  influence: number;
  intent: number;
  risk: number;
  final_score: number;
  reason: string;
};

export type DmEligibility = {
  is_eligible: boolean;
  reason: string;
  evidence_post_id: string;
  opt_out: boolean;
};

export type XUser = {
  id: number;
  x_user_id: string;
  username: string;
  name: string;
  bio: string;
  location: string;
  url: string;
  dm_capability: boolean;
  verified: boolean;
  verified_type: string;
  protected: boolean;
  opt_out: boolean;
  metrics: Record<string, number>;
  last_seen: string;
  score: Score | null;
  dm_eligibility: DmEligibility | null;
};

export type XPost = {
  id: number;
  x_post_id: string;
  text: string;
  lang: string;
  metrics: Record<string, number>;
  query_source: string;
  source_url: string;
  created_at: string;
};

export type LeadCandidate = {
  user: XUser;
  posts: XPost[];
  open_tasks: number;
};

export type EngagementTask = {
  id: number;
  task_type: "public_interaction" | "dm_draft";
  status: "review" | "engage_publicly" | "dm_eligible" | "dm_draft" | "done" | "snoozed" | "rejected" | "opt_out";
  assigned_to: string;
  source_post_id: string;
  draft: string;
  review_notes: string;
  compliance_warning: string;
  created_at: string;
  updated_at: string;
  user: XUser;
  source_post: XPost | null;
};

export type Overview = {
  leads: number;
  review_tasks: number;
  public_tasks: number;
  dm_tasks: number;
  opt_outs: number;
  compliance_blocks: number;
};

export type Session = {
  email: string;
  token: string;
  expires_in: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const TOKEN_KEY = "x-circle-operator-token";
const EMAIL_KEY = "x-circle-operator-email";

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

export function getStoredSession(): { email: string; token: string } | null {
  if (typeof window === "undefined") {
    return null;
  }
  const token = window.localStorage.getItem(TOKEN_KEY);
  const email = window.localStorage.getItem(EMAIL_KEY);
  return token && email ? { email, token } : null;
}

export function clearStoredSession() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(EMAIL_KEY);
}

function storeSession(session: Session) {
  window.localStorage.setItem(TOKEN_KEY, session.token);
  window.localStorage.setItem(EMAIL_KEY, session.email);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const stored = getStoredSession();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(stored?.token ? { Authorization: `Bearer ${stored.token}` } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (response.status === 401 || response.status === 403) {
    clearStoredSession();
    const message = await response.text();
    throw new AuthError(message || "Authentication required");
  }
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function login(email: string) {
  const session = await request<Session>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
  storeSession(session);
  return session;
}

export function logout() {
  clearStoredSession();
}

export function getMe() {
  return request<{ email: string }>("/api/auth/me");
}

export function getOverview() {
  return request<Overview>("/api/overview");
}

export function getLeads() {
  return request<LeadCandidate[]>("/api/leads");
}

export function getTasks() {
  return request<EngagementTask[]>("/api/tasks");
}

export function runSampleDiscovery() {
  return request<{ users_upserted: number; posts_upserted: number; tasks_created: number; warnings: string[] }>("/api/discover/run", {
    method: "POST",
    body: JSON.stringify({ mode: "sample" }),
  });
}

export function updateTask(id: number, body: Partial<Pick<EngagementTask, "status" | "draft" | "review_notes" | "assigned_to">>) {
  return request<EngagementTask>(`/api/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ ...body, actor: "operator" }),
  });
}

export function regenerateDraft(id: number) {
  return request<EngagementTask>(`/api/tasks/${id}/generate-draft`, {
    method: "POST",
  });
}

export function optOut(xUserId: string, reason: string) {
  return request<{ ok: boolean }>("/api/opt-outs", {
    method: "POST",
    body: JSON.stringify({ x_user_id: xUserId, reason, actor: "operator" }),
  });
}
