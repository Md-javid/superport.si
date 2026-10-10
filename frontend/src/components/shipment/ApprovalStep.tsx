"use client";
import { Bot, CheckCircle2, Edit3, RefreshCw, ShieldCheck, ThumbsDown, ThumbsUp, User, XCircle } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { ShipmentDetail } from "@/lib/types";
import { cn, riskColor } from "@/lib/utils";

export function AuditTrail({ shipment }: { shipment: ShipmentDetail }) {
  const events = [...shipment.events].reverse();
  return (
    <Card className="p-6">
      <h3 className="font-display text-base font-bold text-ink">Audit trail</h3>
      <ol className="mt-5 space-y-4">
        {events.slice(0, 12).map((e) => (
          <li key={e.id} className="flex gap-3.5">
            <span className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-full", e.kind === "human" ? "bg-prussian text-white" : "bg-port-50 text-port")}>{e.kind === "human" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}</span>
            <div className="min-w-0">
              <p className="text-sm text-ink">{e.message}</p>
              <p className="text-xs text-ink-faint">{e.actor}, {new Date(e.created_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</p>
              {typeof e.detail?.note === "string" && e.detail.note && <p className="mt-1 rounded-lg bg-alice px-2.5 py-1.5 text-[13px] text-ink-soft">Note: {e.detail.note}</p>}
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

export function ApprovalStep({ shipment, onChange, onDecided, closed }: { shipment: ShipmentDetail; onChange: (s: ShipmentDetail) => void; onDecided: (action: string) => void; closed: boolean }) {
  const toast = useToast();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmReject, setConfirmReject] = useState(false);
  const { risk, compliance, hs_result: hs, hs_decision: dec } = shipment;
  if (!risk || !compliance || !hs) return <Card className="p-10 text-center text-ink-soft">Complete the HS code review to unlock final approval.</Card>;

  const needsNote = risk.level === "high" || compliance.overall === "action_required";
  const editedFields = shipment.documents.reduce((n, d) => n + d.fields.filter((f) => f.edited).length, 0);
  const canDecide = shipment.stage === "final_review";

  async function act(action: string) {
    if (action === "reject" && !confirmReject) return setConfirmReject(true);
    setBusy(action);
    try {
      onChange(await api.decide(shipment.id, action, note || undefined));
      toast({ approve: "Approved. Clearance-ready summary prepared.", reject: "Shipment rejected.", edit: "Reopened for editing.", reanalyze: "Re-analysis complete." }[action] ?? "Done.", action === "approve" ? "success" : "info");
      setNote("");
      setConfirmReject(false);
      onDecided(action);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not record your decision.", "error");
    } finally {
      setBusy(null);
    }
  }

  const findings = [
    { title: "HS classification", ok: dec?.status === "approved" || dec?.status === "edited", text: dec ? `HS ${dec.code} ${dec.status === "edited" ? "(your code)" : "(AI suggestion approved)"}` : "Pending", sub: `AI confidence ${Math.round(hs.confidence * 100)}%` },
    { title: "Compliance", ok: compliance.overall !== "action_required", text: compliance.review_status, sub: `${compliance.alert_count} item${compliance.alert_count === 1 ? "" : "s"} flagged` },
    { title: "Internal risk", ok: risk.level !== "high", text: `${risk.score} / 100, ${risk.label}`, sub: `Main driver: ${risk.main_driver}`, color: riskColor[risk.level] },
    { title: "Extracted data", ok: true, text: editedFields ? `${editedFields} value${editedFields > 1 ? "s" : ""} corrected by you` : "Confirmed without changes", sub: `${shipment.documents.length} of 3 documents on file` },
  ];

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-2xl font-bold text-ink">Review AI findings</h2>
        <p className="mt-1 text-ink-soft">Four findings, one decision. Approve only when you are comfortable with each.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {findings.map((f) => (
          <Card key={f.title} className="p-5">
            <div className="flex items-center justify-between"><p className="text-sm font-semibold text-ink-soft">{f.title}</p>{f.ok ? <CheckCircle2 className="h-5 w-5 text-signal-green" /> : <ShieldCheck className="h-5 w-5 text-signal-amber" />}</div>
            <p className="mt-2 font-display text-lg font-bold" style={f.color ? { color: f.color } : undefined}>{f.text}</p>
            <p className="text-[13px] text-ink-faint">{f.sub}</p>
          </Card>
        ))}
      </div>

      {shipment.stage === "ready" && <div className="flex items-center gap-3 rounded-2xl bg-signal-green/[.08] p-4 text-sm font-semibold text-[#05603A] ring-1 ring-signal-green/25"><CheckCircle2 className="h-5 w-5" /> Approved. The clearance-ready summary is available in the next step.</div>}
      {shipment.stage === "rejected" && <div className="flex items-center gap-3 rounded-2xl bg-signal-red/[.06] p-4 text-sm font-semibold text-[#912018] ring-1 ring-signal-red/25"><XCircle className="h-5 w-5" /> This shipment was rejected.</div>}

      {canDecide && !closed && (
        <Card className="space-y-4 p-6">
          <div className="flex items-center justify-between gap-3"><h3 className="font-display text-base font-bold text-ink">Your decision</h3><Badge tone="blue">Human approval</Badge></div>
          <label className="block">
            <span className="field-label">{needsNote ? "Justification (required to approve)" : "Note (optional)"}</span>
            <textarea rows={3} className={cn("field-input resize-none", needsNote && note.trim().length < 8 && "border-signal-amber/50")} placeholder={needsNote ? "This shipment has open issues or high risk. Explain why it is safe to proceed." : "Add context for the audit trail"} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <div className="flex flex-wrap gap-2.5">
            <Button variant="success" onClick={() => act("approve")} loading={busy === "approve"} disabled={needsNote && note.trim().length < 8}><ThumbsUp className="h-4 w-4" /> Approve</Button>
            <Button variant="secondary" onClick={() => act("edit")} loading={busy === "edit"}><Edit3 className="h-4 w-4" /> Edit data</Button>
            <Button variant="danger" onClick={() => act("reject")} loading={busy === "reject"} onBlur={() => setConfirmReject(false)}><ThumbsDown className="h-4 w-4" /> {confirmReject ? "Confirm reject" : "Reject"}</Button>
            <Button variant="ghost" onClick={() => act("reanalyze")} loading={busy === "reanalyze"}><RefreshCw className="h-4 w-4" /> Request re-analysis</Button>
          </div>
        </Card>
      )}

      <AuditTrail shipment={shipment} />
    </div>
  );
}
