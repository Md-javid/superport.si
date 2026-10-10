"use client";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Edit3, HelpCircle, RefreshCw, Sparkles, ThumbsDown, ThumbsUp, XCircle } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, ProgressBar, Ring } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { ShipmentDetail } from "@/lib/types";
import { EvidenceList } from "./EvidenceList";

export function HsStep({ shipment, onChange, onDecided, closed }: { shipment: ShipmentDetail; onChange: (s: ShipmentDetail) => void; onDecided: () => void; closed: boolean }) {
  const toast = useToast();
  const hs = shipment.hs_result;
  const decision = shipment.hs_decision;
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  if (!hs) return <Card className="p-10 text-center text-ink-soft">Confirm the extracted data to get an HS code recommendation.</Card>;

  const confTone = hs.confidence >= 0.85 ? "#12B76A" : hs.confidence >= 0.65 ? "#F79009" : "#F04438";

  async function act(action: string, hsCode?: string) {
    setBusy(action);
    try {
      onChange(await api.reviewHs(shipment.id, action, hsCode, note || undefined));
      const msg = { approve: "HS code approved.", edit: "HS code updated.", reject: "Recommendation rejected.", reanalyze: "Re-analysis complete." }[action];
      toast(msg ?? "Done.", action === "reject" ? "info" : "success");
      setEditing(false);
      setNote("");
      if (action === "approve" || action === "edit") onDecided();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not save your decision.", "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-2xl font-bold text-ink">HS code recommendation</h2>
        <p className="mt-1 text-ink-soft">The copilot suggests a classification and shows its evidence. You make the call.</p>
      </div>

      <div className="relative overflow-hidden rounded-2xl border border-signal-amber/30 bg-gradient-to-r from-signal-amber/[.09] via-white to-white p-4">
        <div className="flex items-center gap-2.5 text-sm font-bold text-[#93370D]"><Sparkles className="h-4 w-4" /> AI Recommendation — Human Review Required</div>
      </div>

      {hs.fallback_reason && (
        <div className="flex gap-3 rounded-2xl border border-signal-amber/30 bg-signal-amber/[.07] p-4 text-sm text-[#7A2E0E]"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><p>{hs.fallback_reason} Showing the rule-based demo suggestion instead.</p></div>
      )}
      {hs.engine.startsWith("demo-rules") && !hs.fallback_reason && (
        <div className="flex gap-3 rounded-2xl border border-alice-200 bg-white p-4 text-sm text-ink-soft"><Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-port" /><p>This is the rule-based demo classification. Turn on live intelligence to get an evidence-backed recommendation from Gemini and web sources.</p></div>
      )}
      {hs.grounded === "none" && hs.engine.startsWith("gemini") && (
        <div className="flex gap-3 rounded-2xl border border-signal-amber/30 bg-signal-amber/[.07] p-4 text-sm text-[#7A2E0E]"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><p>The suggested code was not found in the sources we retrieved. Check it against the official tariff before approving.</p></div>
      )}

      <Card className="overflow-hidden">
        <div className="grid gap-6 p-6 md:grid-cols-[1fr_auto]">
          <div>
            <p className="text-[13px] font-medium text-ink-faint">Product description</p>
            <p className="mt-1 text-[15px] font-medium text-ink">{hs.product_description}</p>
            <p className="mt-5 text-[13px] font-medium text-ink-faint">Suggested HS code</p>
            <motion.p key={hs.code} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-1 font-display text-5xl font-extrabold tracking-tight text-prussian">{decision?.code && decision.code !== hs.code ? <span className="text-ink-faint line-through decoration-2">{hs.code}</span> : hs.code}</motion.p>
            <p className="mt-2 text-sm font-semibold text-ink">{hs.label}</p>
            <p className="text-sm text-ink-soft">{hs.chapter}</p>
          </div>
          <div className="flex items-center gap-4 md:flex-col md:items-center md:justify-center">
            <Ring value={hs.confidence * 100} size={112} stroke={10} color={confTone}><div className="text-center"><p className="font-display text-2xl font-extrabold text-ink">{Math.round(hs.confidence * 100)}%</p><p className="text-[11px] font-medium text-ink-faint">confidence</p></div></Ring>
          </div>
        </div>
        <div className="border-t border-alice-200/70 bg-alice/50 px-6 py-4 text-sm leading-relaxed text-ink-soft">{hs.rationale}<p className="mt-2 text-xs text-ink-faint">Engine: {hs.engine}</p></div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="p-6">
          <h3 className="font-display text-base font-bold text-ink">Supporting evidence</h3>
          <ul className="mt-4 space-y-3">
            {hs.evidence.map((e, i) => (
              <motion.li key={e} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.07 }} className="flex gap-3 text-sm text-ink"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-signal-green" />{e}</motion.li>
            ))}
          </ul>
        </Card>
        <Card className="p-6">
          <h3 className="font-display text-base font-bold text-ink">Alternative classifications</h3>
          <ul className="mt-4 space-y-3.5">
            {hs.alternatives.map((a) => (
              <li key={a.code} className="rounded-xl border border-alice-200 p-3.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0"><p className="font-display font-bold text-ink">{a.code}</p><p className="text-sm text-ink-soft">{a.label}</p></div>
                  {!closed && <Button variant="ghost" size="sm" disabled={busy !== null} onClick={() => act("edit", a.code)}>Use this</Button>}
                </div>
                <div className="mt-2.5 flex items-center gap-2.5"><ProgressBar value={a.confidence * 100} color="#8CB0FA" className="flex-1" /><span className="text-xs font-semibold text-ink-soft">{Math.round(a.confidence * 100)}%</span></div>
                <p className="mt-2 text-[13px] leading-snug text-ink-faint">Why not: {a.why_not}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {hs.needs_info && hs.needs_info.length > 0 && (
        <Card className="p-6">
          <h3 className="flex items-center gap-2 font-display text-base font-bold text-ink"><HelpCircle className="h-4 w-4 text-port" /> Would raise confidence</h3>
          <ul className="mt-3 space-y-2">{hs.needs_info.map((n) => <li key={n} className="text-sm text-ink-soft">{n}</li>)}</ul>
          <p className="mt-3 text-xs text-ink-faint">Add this detail to the product description or documents, then request re-analysis.</p>
        </Card>
      )}

      {hs.sources && hs.sources.length > 0 && (
        <Card className="p-6">
          <h3 className="font-display text-base font-bold text-ink">Web evidence</h3>
          <p className="mb-4 mt-1 text-sm text-ink-soft">Sources found while classifying. Web results are signals to check, not final authority.</p>
          <EvidenceList sources={hs.sources} mode={hs.sources_mode} />
        </Card>
      )}

      {decision && (
        <div className={`flex items-start gap-3 rounded-2xl p-4 text-sm ring-1 ${decision.status === "rejected" ? "bg-signal-red/[.06] text-[#912018] ring-signal-red/25" : "bg-signal-green/[.07] text-[#05603A] ring-signal-green/25"}`}>
          {decision.status === "rejected" ? <XCircle className="mt-0.5 h-4 w-4" /> : <CheckCircle2 className="mt-0.5 h-4 w-4" />}
          <p>{decision.status === "approved" && <>You approved HS {decision.code}.</>}{decision.status === "edited" && <>You set HS {decision.code} (AI suggested {decision.ai_code}).</>}{decision.status === "rejected" && <>You rejected the recommendation. Pick an alternative, enter a code, or request re-analysis.</>}</p>
        </div>
      )}

      {!closed && (
        <Card className="space-y-4 p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-display text-base font-bold text-ink">Your decision</h3>
            <Badge tone="blue">Human approval</Badge>
          </div>
          <textarea rows={2} className="field-input resize-none" placeholder="Add a note for the audit trail (optional)" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Decision note" />
          {editing && (
            <div className="flex flex-wrap items-end gap-3 rounded-xl bg-port-50/60 p-3">
              <label className="min-w-[180px] flex-1"><span className="field-label">Your HS code</span><input autoFocus className="field-input" placeholder="e.g. 8507.60" value={code} onChange={(e) => setCode(e.target.value)} /></label>
              <Button onClick={() => act("edit", code)} loading={busy === "edit"}>Save code</Button>
              <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
            </div>
          )}
          <div className="flex flex-wrap gap-2.5">
            <Button variant="success" onClick={() => act("approve")} loading={busy === "approve"}><ThumbsUp className="h-4 w-4" /> Approve {hs.code}</Button>
            <Button variant="secondary" onClick={() => { setEditing((e) => !e); setCode(hs.code); }}><Edit3 className="h-4 w-4" /> Edit code</Button>
            <Button variant="danger" onClick={() => act("reject")} loading={busy === "reject"}><ThumbsDown className="h-4 w-4" /> Reject</Button>
            <Button variant="ghost" onClick={() => act("reanalyze")} loading={busy === "reanalyze"}><RefreshCw className="h-4 w-4" /> Request re-analysis</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
