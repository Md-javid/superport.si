"use client";
import { CheckCheck, ExternalLink, Info, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { Signal } from "@/lib/types";

export const EVENT_LABEL: Record<string, string> = { strike: "Strike", congestion: "Congestion", weather: "Weather", tariff_change: "Tariff change", regulation: "Regulation", closure: "Closure", carrier: "Carrier", geopolitical: "Geopolitical", other: "Event" };
const SEV: Record<string, Tone> = { low: "gray", medium: "amber", high: "red" };

export function verificationLabel(s: Signal) {
  const n = new Set(s.sources.map((x) => x.source || x.url)).size;
  return s.verification === "official" ? "Official source found" : s.verification === "corroborated" ? `Corroborated by ${n} sources` : "Unverified: 1 source";
}

export function SignalCard({ signal, onReview }: { signal: Signal; onReview?: (id: number, action: "acknowledge" | "dismiss", note: string) => Promise<void> }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  async function act(action: "acknowledge" | "dismiss") {
    if (!onReview) return;
    setBusy(action);
    try { await onReview(signal.id, action, note); } finally { setBusy(null); }
  }
  return (
    <article className="surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={SEV[signal.severity]} dot>{signal.severity === "high" ? "High impact" : signal.severity === "medium" ? "Medium impact" : "Low impact"}</Badge>
            <Badge tone="blue">{EVENT_LABEL[signal.event_type] ?? "Event"}</Badge>
            {signal.source_mode === "fixture" && <Badge tone="amber">Sample data</Badge>}
            {signal.status !== "new" && <Badge tone="gray">{signal.status === "acknowledged" ? "Acknowledged" : "Dismissed"}</Badge>}
          </div>
          <h3 className="mt-2 font-display text-lg font-bold text-ink">{signal.title}</h3>
          <p className="mt-1 text-sm leading-relaxed text-ink-soft">{signal.summary}</p>
        </div>
        <div className="text-right">
          <p className="font-display text-2xl font-extrabold text-ink">{Math.round(signal.confidence * 100)}%</p>
          <p className="text-xs text-ink-faint">confidence</p>
        </div>
      </div>
      <p className="mt-3 flex items-center gap-1.5 text-xs font-semibold text-ink-soft"><Info className="h-3.5 w-3.5 text-port" /> {verificationLabel(signal)}. This is a signal, not a confirmed fact.</p>

      {signal.affected.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold text-ink-faint">Affected shipments</p>
          <ul className="mt-1.5 flex flex-wrap gap-2">{signal.affected.map((a) => (
            <li key={a.shipment_id}><Link href={`/shipments/${a.shipment_id}`} className="inline-flex items-center gap-1.5 rounded-lg bg-port-50 px-2.5 py-1.5 text-xs font-semibold text-port-600 hover:bg-port hover:text-white" title={a.reason}>{a.reference}<span className="font-normal opacity-80">{a.reason}</span></Link></li>
          ))}</ul>
        </div>
      )}

      <details className="mt-4">
        <summary className="cursor-pointer text-sm font-semibold text-port">Sources ({signal.sources.length})</summary>
        <ul className="mt-2 space-y-2">{signal.sources.map((s) => (
          <li key={s.url} className="text-[13px]"><a href={s.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 font-semibold text-ink hover:text-port">{s.title}<ExternalLink className="h-3 w-3" /></a><p className="text-xs text-ink-faint">{s.source}{s.date ? `, ${s.date}` : ""}</p></li>
        ))}</ul>
      </details>

      {onReview && signal.status === "new" && (
        <div className="mt-4 flex flex-wrap items-center gap-2.5 border-t border-alice-200 pt-4">
          <input className="field-input !py-2 min-w-[200px] flex-1" placeholder="Note (optional), for example who you informed" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Review note" />
          <Button size="sm" variant="success" onClick={() => act("acknowledge")} loading={busy === "acknowledge"}><CheckCheck className="h-4 w-4" /> Acknowledge</Button>
          <Button size="sm" variant="secondary" onClick={() => act("dismiss")} loading={busy === "dismiss"}><X className="h-4 w-4" /> Dismiss</Button>
        </div>
      )}
    </article>
  );
}
