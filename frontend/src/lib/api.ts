import type { CopilotAnswer, Draft, LibraryDoc, LibraryHit, RagStatus, SerpApiShowcase, ControlTower, InvitationInfo, TrackingSummary, NotificationItem, PartyRole, TeamData, Workspace, ClearanceSummary, DashboardData, DocType, EvidenceItem, IntelligenceStatus, ScanSummary, Signal, ShipmentDetail, ShipmentSummary, User } from "./types";

const TOKEN_KEY = "superport.token";

export const tokenStore = {
  get: () => (typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY) || window.sessionStorage.getItem(TOKEN_KEY)),
  set: (token: string, remember: boolean) => {
    window.localStorage.removeItem(TOKEN_KEY);
    window.sessionStorage.removeItem(TOKEN_KEY);
    (remember ? window.localStorage : window.sessionStorage).setItem(TOKEN_KEY, token);
  },
  clear: () => {
    window.localStorage.removeItem(TOKEN_KEY);
    window.sessionStorage.removeItem(TOKEN_KEY);
  },
};

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { ...init, headers });
  } catch {
    throw new ApiError("Cannot reach the SuperPort API. Check that the backend is running on port 8000.", 0);
  }
  if (!res.ok) {
    let message = "Something went wrong. Try again.";
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { loc?: string[]; msg: string }) => `${d.loc?.slice(-1)[0] ?? "field"}: ${d.msg}`).join(". ");
    } catch {}
    if (res.status === 401 && !path.startsWith("/auth/login") && typeof window !== "undefined") {
      tokenStore.clear();
      window.location.href = "/login";
    }
    throw new ApiError(message, res.status);
  }
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  login: (email: string, password: string, remember: boolean) => post<{ token: string; user: User }>("/auth/login", { email, password, remember }),
  demoLogin: (persona = "broker") => post<{ token: string; user: User }>(`/auth/demo?persona=${persona}`),
  register: (body: { org_name: string; org_type: PartyRole; name: string; email: string; password: string; invite_token?: string }) =>
    post<{ token: string; user: User; dev_link: string | null; joined_shipment_id: number | null }>("/auth/register", body),
  verifyEmail: (token: string) => post<User>("/auth/verify-email", { token }),
  resendVerification: () => post<{ already_verified: boolean; dev_link: string | null }>("/auth/resend-verification"),
  forgotPassword: (email: string) => post<{ message: string; dev_link: string | null }>("/auth/forgot-password", { email }),
  resetPassword: (token: string, password: string) => post<{ message: string }>("/auth/reset-password", { token, password }),
  invitation: (token: string) => request<InvitationInfo>(`/invitations/${token}`),
  acceptInvitation: (token: string) => post<{ shipment_id: number }>(`/invitations/${token}/accept`),
  team: () => request<TeamData>("/team"),
  inviteTeammate: (email: string) => post<{ id: number; email: string; dev_link: string | null }>("/team/invitations", { email }),
  notifications: () => request<{ unread: number; items: NotificationItem[] }>("/notifications").catch(() => ({ unread: 0, items: [] })),
  markRead: (ids: number[] = []) => post<{ ok: boolean }>("/notifications/read", { ids }).catch(() => ({ ok: false })),
  workspace: (id: number | string) => request<Workspace>(`/shipments/${id}/workspace`),
  addComment: (id: number, body: string) => post<{ ok: boolean }>(`/shipments/${id}/comments`, { body }),
  inviteToShipment: (id: number, email: string, party_role: PartyRole) => post<{ id: number; email: string; dev_link: string | null }>(`/shipments/${id}/invitations`, { email, party_role }),
  removeParticipant: (id: number, orgId: number) => request<{ ok: boolean }>(`/shipments/${id}/participants/${orgId}`, { method: "DELETE" }),
  addChecklistItem: (id: number, label: string, party_role: PartyRole) => post<{ ok: boolean }>(`/shipments/${id}/checklist`, { label, party_role, required: true }),
  uploadChecklist: (id: number, itemId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ ok: boolean }>(`/shipments/${id}/checklist/${itemId}/upload`, { method: "POST", body: form });
  },
  updateTimeline: (id: number, key: string, body: { status?: string; planned_at?: string; actual_at?: string; note?: string }) => post<{ ok: boolean }>(`/shipments/${id}/timeline/${key}`, body),
  refreshTracking: (id: number) => post<TrackingSummary>(`/shipments/${id}/tracking/refresh`),
  controlTower: () => request<ControlTower>("/control-tower"),
  ask: (id: number, question: string) => post<CopilotAnswer>(`/shipments/${id}/copilot/ask`, { question }),
  copilotHistory: (id: number) => request<CopilotAnswer[]>(`/shipments/${id}/copilot/history`),
  draftUpdate: (id: number, audience: PartyRole) => post<Draft>(`/shipments/${id}/copilot/draft-update`, { audience }),
  sendUpdate: (id: number, to_roles: PartyRole[], subject: string, body: string) => post<{ sent_to: number }>(`/shipments/${id}/updates/send`, { to_roles, subject, body }),
  library: () => request<{ status: RagStatus; documents: LibraryDoc[] }>("/knowledge"),
  uploadLibrary: (file: File, title: string, tags: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    form.append("tags", tags);
    return request<LibraryDoc>("/knowledge", { method: "POST", body: form });
  },
  deleteLibrary: (id: number) => request<{ ok: boolean }>(`/knowledge/${id}`, { method: "DELETE" }),
  searchLibrary: (query: string, scope: "library" | "org") => post<LibraryHit[]>("/knowledge/search", { query, scope, k: 6 }),
  reindexLibrary: () => post<{ chunks: number }>("/knowledge/reindex"),
  indexShipments: () => post<{ chunks: number }>("/knowledge/index-shipments"),
  serpapiShowcase: () => request<SerpApiShowcase>("/intelligence/serpapi"),
  remind: (id: number, itemId: number) => post<{ notified: number }>(`/shipments/${id}/checklist/${itemId}/remind`),
  downloadChecklist: async (id: number, itemId: number, filename: string) => {
    const res = await fetch(`/api/shipments/${id}/checklist/${itemId}/file`, { headers: { Authorization: `Bearer ${tokenStore.get() ?? ""}` } });
    if (!res.ok) throw new ApiError("Could not download the file.", res.status);
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "document";
    a.click();
    URL.revokeObjectURL(url);
  },
  me: () => request<User>("/auth/me"),
  dashboard: () => request<DashboardData>("/dashboard"),
  shipments: () => request<ShipmentSummary[]>("/shipments"),
  shipment: (id: number | string) => request<ShipmentDetail>(`/shipments/${id}`),
  createShipment: (body: Record<string, string>) => post<ShipmentDetail>("/shipments", body),
  uploadDocument: (id: number, docType: DocType, file: File) => {
    const form = new FormData();
    form.append("doc_type", docType);
    form.append("file", file);
    return request<ShipmentDetail>(`/shipments/${id}/documents`, { method: "POST", body: form });
  },
  useSamples: (id: number) => post<ShipmentDetail>(`/shipments/${id}/documents/samples`),
  process: (id: number) => post<ShipmentDetail>(`/shipments/${id}/process`),
  editField: (id: number, docId: number, key: string, value: string) =>
    request<ShipmentDetail>(`/shipments/${id}/documents/${docId}/fields/${key}`, { method: "PATCH", body: JSON.stringify({ value }) }),
  confirmExtraction: (id: number) => post<ShipmentDetail>(`/shipments/${id}/extraction/confirm`),
  reviewHs: (id: number, action: string, hs_code?: string, note?: string) => post<ShipmentDetail>(`/shipments/${id}/hs/review`, { action, hs_code, note }),
  decide: (id: number, action: string, note?: string) => post<ShipmentDetail>(`/shipments/${id}/decision`, { action, note }),
  verify: (id: number, parts?: string[], force = false) => post<ShipmentDetail>(`/shipments/${id}/verify`, { parts: parts ?? ["price", "company", "rules"], force }),
  radarSignals: (status: "active" | "all" = "active") => request<Signal[]>(`/radar/signals?status=${status}`),
  radarScan: (force = false) => post<ScanSummary>("/radar/scan", { force }),
  radarReview: (id: number, action: "acknowledge" | "dismiss", note?: string) => post<Signal>(`/radar/signals/${id}/review`, { action, note: note ?? "" }),
  shipmentSignals: (id: number) => request<Signal[]>(`/shipments/${id}/signals`),
  evidence: (id: number) => request<EvidenceItem[]>(`/shipments/${id}/evidence`),
  intelligence: () => request<IntelligenceStatus>(`/intelligence/status`),
  summary: (id: number) => request<ClearanceSummary>(`/shipments/${id}/summary`),
};
