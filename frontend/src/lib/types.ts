export type Stage = "draft" | "documents" | "extraction_review" | "hs_review" | "final_review" | "ready" | "rejected";
export type RiskLevel = "low" | "medium" | "high";
export type DocType = "commercial_invoice" | "packing_list" | "bill_of_lading";

export interface User { id: number; email: string; name: string; role: string; company: string; org_id: number | null; org_name: string; org_type: PartyRole | ""; org_role: "admin" | "member"; email_verified: boolean }
export type PartyRole = "broker" | "forwarder" | "importer" | "exporter"

export interface ShipmentSummary {
  id: number; reference: string; importer: string; exporter: string; origin: string; destination: string;
  port: string; carrier: string; container_number: string; product_description: string;
  stage: Stage; stage_label: string; progress: number; documents_count: number;
  risk_score: number | null; risk_level: RiskLevel | null; alerts: number; hs_code: string | null; is_demo: boolean; access: "owner" | "partner"; party_role: PartyRole | null; shared_by: string | null; open_requests: number;
  created_at: string; updated_at: string;
}

export interface ExtractedField {
  key: string; label: string; value: string; original: string; confidence: number;
  source: "extracted" | "gemini-vision" | "demo-synthesized" | "edited" | "not-found"; edited: boolean;
}
export interface DocumentOut {
  id: number; doc_type: DocType; label: string; filename: string; size_bytes: number;
  status: "uploaded" | "ready"; fields: ExtractedField[]; meta: Record<string, unknown>; created_at: string;
}
export interface HsAlternative { code: string; label: string; why_not: string; confidence: number }
export interface HsResult {
  product_description: string; code: string; label: string; chapter: string; confidence: number;
  evidence: string[]; alternatives: HsAlternative[]; rationale: string; item_key: string; engine: string;
  sources?: WebSource[]; sources_mode?: "live" | "fixture" | "none"; grounded?: "code" | "heading" | "none";
  needs_info?: string[]; source_notes?: string[]; fallback_reason?: string | null;
}
export interface WebSource { index: number; title: string; url: string; snippet: string; trust: "official" | "reference" | "web" }
export interface EvidenceItem { id: number; kind: string; engine: string; query: string; title: string; url: string; snippet: string; trust: "official" | "reference" | "web"; source_mode: "live" | "fixture"; retrieved_at: string }
export interface IntelligenceStatus {
  mode: "off" | "fixtures" | "live";
  gemini: { configured: boolean; fast_model: string; pro_model: string };
  serpapi: { configured: boolean };
  budgets: { serpapi_per_shipment: number; gemini_per_shipment: number; cache_ttl_hours: number };
  usage_30d: Record<"serpapi" | "gemini", { live_calls: number; cache_hits: number; failed: number; tokens_in: number; tokens_out: number }>;
  warnings: string[]; note: string;
}
export interface HsDecision { status: "approved" | "edited" | "rejected"; code: string | null; by: string; note: string; ai_code?: string }
export type ItemStatus = "ok" | "info" | "warn" | "issue";
export interface ComplianceItem { id: string; title: string; status: ItemStatus; summary: string; details: string[] }
export interface Inconsistency { field: string; severity: "warn" | "issue"; message: string; values: Record<string, string> }
export interface Compliance {
  overall: "clear" | "needs_review" | "action_required"; review_status: string; items: ComplianceItem[];
  missing_documents: string[]; restrictions: string[]; certificates: { name: string; status: string; source?: number }[]; rules_basis?: string;
  inconsistencies: Inconsistency[]; alert_count: number; rules: string;
}
export interface RiskFactor { key: string; label: string; score: number; weight: number; contribution: number; level: RiskLevel; explanation: string; basis?: string }
export interface Risk { score: number; level: RiskLevel; label: string; headline: string; main_driver: string; factors: RiskFactor[]; disclaimer: string }
export interface Brief { happened: string; why: string; recommendation: string; approval: string; next: string }
export interface AuditEvent { id: number; actor: string; kind: "system" | "human"; action: string; message: string; detail: Record<string, unknown> | null; created_at: string }

export interface ShipmentDetail extends ShipmentSummary {
  documents: DocumentOut[]; missing_documents: DocType[]; hs_result: HsResult | null; hs_decision: HsDecision | null;
  compliance: Compliance | null; risk: Risk | null; brief: Brief; events: AuditEvent[]; analysis_runs: number;
  eta: EtaEstimate; intel: Intel | null; verification: { available: boolean; reason: string | null; sample: boolean };
}

export interface Agent { name: string; title: string; description: string; phase: number; status: "active" | "planned" }
export interface DashboardData {
  kpis: { active_shipments: number; pending_documents: number; pending_documents_shipments: number; compliance_alerts: number; high_risk: number; clearance_progress: number };
  stage_counts: Record<string, number>;
  recent: ShipmentSummary[];
  shared: ShipmentSummary[];
  attention: (ShipmentSummary & { action: string })[];
  agents: Agent[];
  ai: { mode: string; ocr: string; llm: string; note: string };
  intelligence: IntelligenceStatus;
}

export interface ClearanceSummary {
  reference: string; status: Stage; status_label: string;
  parties: { importer: string; exporter: string };
  route: { origin: string; destination: string; port: string; carrier: string; container: string; vessel?: string };
  goods: Record<string, string | null>;
  hs: { code: string | null; decision: string | null; ai_code: string | null; confidence: number | null };
  compliance: { review_status: string | null; open_items: string[]; certificates: { name: string; status: string }[] };
  risk: { score: number | null; label: string | null };
  approvals: AuditEvent[];
  disclaimer: string;
}

export const DOC_LABELS: Record<DocType, string> = {
  commercial_invoice: "Commercial Invoice",
  packing_list: "Packing List",
  bill_of_lading: "Bill of Lading",
};

export interface PriceCheck {
  status: "ok" | "inconclusive" | "not_comparable" | "unavailable"; summary: string; source_mode: "live" | "fixture";
  unit_price?: number; market?: { n: number; median: number; p25: number; p75: number; min: number; max: number }; ratio?: number; level?: RiskLevel;
  listings?: { title: string; price: number; source: string; url: string }[]; filtered_by_ai?: boolean; notes?: string;
}
export interface PartyCheck {
  role: string; name: string; country: string; level: "low" | "medium" | "high" | "unknown"; summary: string;
  place: { title: string; address: string; rating?: number | null; reviews?: number | null; website?: string; type?: string } | null;
  articles: { title: string; url: string; source: string; date: string; trust: "official" | "reference" | "web"; verdict: "adverse" | "possible"; reason: string }[];
}
export interface CompanyCheck { status: "ok" | "unavailable"; summary?: string; source_mode: "live" | "fixture"; parties?: PartyCheck[]; overall_level?: "low" | "medium" | "high" | "unknown"; screened_by_ai?: boolean; disclaimer?: string }
export interface RulesLookup {
  status: "ok" | "sources_only" | "no_findings" | "unavailable"; summary: string; source_mode: "live" | "fixture"; hs_code?: string; sources?: WebSource[];
  restrictions?: { text: string; source: number }[]; certificates?: { name: string; source: number; level: "required" | "likely" | "unsure" }[]; duty_notes?: { text: string; source: number }[];
}
export interface Intel { price?: PriceCheck; company?: CompanyCheck; rules?: RulesLookup; updated_at?: string }

export interface Signal {
  id: number; event_type: string; title: string; summary: string; severity: RiskLevel; confidence: number;
  verification: "single-source" | "corroborated" | "official"; locations: string[]; products: string[];
  sources: { title: string; url: string; source: string; date: string; trust: "official" | "reference" | "web" }[];
  engine: string; source_mode: "live" | "fixture"; status: "new" | "acknowledged" | "dismissed"; review_note: string;
  carriers?: string[]; first_seen: string; last_seen: string; affected: { shipment_id: number; reference: string; reason: string }[];
}
export interface ScanSummary { queries: number; articles: number; events: number; new: number; updated: number; matched: number; errors: string[]; engine: string; sample?: boolean; note?: string }

export interface ChecklistItem { id: number; key: string; label: string; party_role: PartyRole; required: boolean; status: "missing" | "uploaded"; filename: string; size_bytes: number; uploaded_by: string; uploaded_at: string | null; last_reminder_at: string | null; core: boolean; can_download: boolean }
export interface Participant { org_id: number; org_name: string; party_role: PartyRole; owner: boolean; members: string[] }
export interface WorkspaceComment { id: number; author: string; org_name: string; party_role: PartyRole | ""; body: string; created_at: string; mine: boolean }
export interface Workspace {
  shipment: { id: number; reference: string; importer: string; exporter: string; origin: string; destination: string; port: string; carrier: string; container_number: string; product_description: string; stage_label: string; stage: Stage; progress: number };
  access: "owner" | "partner"; party_role: PartyRole | null; owner_org: string; participants: Participant[];
  pending_invitations: { id: number; email: string; party_role: PartyRole; expires_at: string }[];
  timeline: TimelineStep[]; tracking: TrackingSummary; eta: EtaEstimate;
  checklist: ChecklistItem[]; comments: WorkspaceComment[]; activity: { id: number; actor: string; message: string; created_at: string }[]; can_manage: boolean; can_invite: boolean;
}
export interface NotificationItem { id: number; kind: string; title: string; body: string; link: string; read: boolean; created_at: string; shipment_id: number | null }
export interface TeamData { org: { id: number; name: string; type: PartyRole }; members: { id: number; name: string; email: string; org_role: string; email_verified: boolean }[]; invitations: { id: number; email: string; expires_at: string }[]; can_invite: boolean }
export interface InvitationInfo { kind: "shipment" | "team"; email: string; inviter_org: string; party_role: PartyRole | null; shipment_reference: string | null; expires_at: string }
export const PARTY_LABEL: Record<PartyRole, string> = { broker: "Customs broker", forwarder: "Freight forwarder", importer: "Importer", exporter: "Exporter" };

export type StepStatus = "pending" | "current" | "done" | "delayed" | "blocked";
export interface TimelineStep { key: string; label: string; status: StepStatus; planned_at: string | null; actual_at: string | null; source: "system" | "manual" | "tracking"; note: string; updated_by: string; can_update: boolean }
export interface EtaEstimate {
  eta: string | null; baseline?: string; earliest?: string; latest?: string; delay_days: number; confidence?: number; risk?: "low" | "moderate" | "high";
  basis: string; drivers: { label: string; days: number; kind: "signal" | "documents"; detail: string }[]; arrived: boolean; message: string;
}
export interface TrackingSummary {
  connected: boolean; provider: string; sample: boolean; fetched_at: string | null; status: string | null; location: string | null; vessel: string | null; voyage: string | null; eta: string | null;
  events: { time: string; location: string; description: string; key: string | null }[]; container: { number: string; valid: boolean; reason: string }; search_url: string; can_refresh: boolean;
}
export type TowerCategory = "customs_hold" | "port_event" | "vessel_delay" | "missing_document" | "needs_review" | "cleared";
export interface TowerShipment {
  id: number; reference: string; product: string; route: string; port: string; access: "owner" | "partner"; party_role: PartyRole | null; stage_label: string; eta: string | null; delay_days: number;
  exceptions: { category: TowerCategory; severity: "red" | "amber" | "green"; title: string; detail: string }[]; severity: "red" | "amber" | "green"; link: string; workspace_link: string; on_track: boolean;
}
export interface ControlTower { counts: Record<TowerCategory, number>; labels: Record<TowerCategory, string>; shipments: TowerShipment[]; total: number }
