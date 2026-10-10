"use client";
import { AlertTriangle, Check, CircleDot, ExternalLink, Gauge, RefreshCw, Ship, XOctagon } from "lucide-react";
import { useState } from "react";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, SectionTitle } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { StepStatus, TimelineStep, Workspace } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";

const DOT: Record<StepStatus, string> = { done: "bg-signal-green text-white", current: "bg-port text-white ring-4 ring-port/20", pending: "bg-alice-200 text-ink-faint", delayed: "bg-signal-amber text-white", blocked: "bg-signal-red text-white" };
const LABEL: Record<StepStatus, string> = { done: "Done", current: "In progress", pending: "Not started", delayed: "Delayed", blocked: "On hold" };
const RISK: Record<string, Tone> = { low: "green", moderate: "amber", high: "red" };
const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" }) : "");

function StepForm({ step, shipmentId, onDone }: { step: TimelineStep; shipmentId: number; onDone: () => void }) {
  const toast = useToast();
  const options: StepStatus[] = step.key === "customs_clearance" ? ["pending", "delayed", "blocked"] : ["pending", "current", "done", "delayed", "blocked"];
  const [status, setStatus] = useState<StepStatus>(options.includes(step.status) ? step.status : options[0]);
  const [planned, setPlanned] = useState(step.planned_at ? step.planned_at.slice(0, 10) : "");
  const [note, setNote] = useState(step.note);
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    try {
      await api.updateTimeline(shipmentId, step.key, { status, planned_at: planned || undefined, note });
      toast(`${step.label} updated.`, "success");
      onDone();
    } catch (e) { toast(e instanceof Error ? e.message : "Could not update.", "error"); } finally { setBusy(false); }
  }
  return (
    <div className="mt-3 grid gap-2.5 rounded-xl bg-alice/70 p-3.5 sm:grid-cols-[150px_150px_1fr_auto]">
      <select className="field-input !py-2" value={status} onChange={(e) => setStatus(e.target.value as StepStatus)} aria-label="Status">{options.map((o) => <option key={o} value={o}>{LABEL[o]}</option>)}</select>
      <input className="field-input !py-2" type="date" value={planned} onChange={(e) => setPlanned(e.target.value)} aria-label="Planned date" title="Planned date" />
      <input className="field-input !py-2" placeholder={status === "delayed" || status === "blocked" ? "Reason (required)" : "Note (optional)"} value={note} onChange={(e) => setNote(e.target.value)} aria-label="Note" />
      <Button size="sm" onClick={save} loading={busy}>Save</Button>
    </div>
  );
}

export function TimelinePanel({ shipmentId, ws, onChanged }: { shipmentId: number; ws: Workspace; onChanged: () => void }) {
  const toast = useToast();
  const [editing, setEditing] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const { eta, tracking } = ws;

  async function refresh() {
    setRefreshing(true);
    try { await api.refreshTracking(shipmentId); toast("Tracking refreshed.", "success"); onChanged(); }
    catch (e) { toast(e instanceof Error ? e.message : "Could not refresh tracking.", "error"); } finally { setRefreshing(false); }
  }

  return (
    <Card className="p-6">
      <SectionTitle title="Shipment timeline" hint="One source of truth for where the cargo is." />
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-alice-200 p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-ink-soft"><Gauge className="h-4 w-4 text-port" /> Expected arrival</p>
          {eta.eta ? (<>
            <p className="mt-1 font-display text-3xl font-extrabold text-ink">{fmt(eta.eta)}</p>
            <p className="text-sm text-ink-soft">{eta.delay_days > 0 ? `${eta.delay_days} day${eta.delay_days > 1 ? "s" : ""} later than the baseline of ${fmt(eta.baseline ?? null)}` : "On the baseline date"}. Likely between {fmt(eta.earliest ?? null)} and {fmt(eta.latest ?? null)}.</p>
            <div className="mt-2 flex flex-wrap gap-2"><Badge tone={RISK[eta.risk ?? "low"]} dot>{eta.risk} delay risk</Badge><Badge tone="gray">{Math.round((eta.confidence ?? 0) * 100)}% confidence</Badge><Badge tone="blue">Basis: {eta.basis}</Badge></div>
            {eta.drivers.length > 0 && <ul className="mt-3 space-y-1.5">{eta.drivers.map((d) => <li key={d.label} className="text-[13px] text-ink-soft"><span className="font-semibold text-ink">+{d.days} d</span> {d.label} <span className="text-ink-faint">({d.detail})</span></li>)}</ul>}
          </>) : <p className="mt-2 text-sm text-ink-soft">{eta.message}</p>}
          <p className="mt-3 text-xs text-ink-faint">{eta.eta ? eta.message : ""}</p>
        </div>

        <div className="rounded-xl border border-alice-200 p-4">
          <div className="flex items-start justify-between gap-2">
            <p className="flex items-center gap-2 text-sm font-semibold text-ink-soft"><Ship className="h-4 w-4 text-port" /> Container tracking</p>
            {tracking.connected ? <Badge tone={tracking.sample ? "amber" : "green"}>{tracking.sample ? "Sample data" : tracking.provider}</Badge> : <Badge>Not connected</Badge>}
          </div>
          <p className="mt-1 font-mono text-sm font-semibold text-ink">{tracking.container.number}</p>
          <p className={cn("text-xs", tracking.container.valid ? "text-[#067647]" : "text-[#B54708]")}>{tracking.container.valid ? "Valid container number (ISO 6346)." : tracking.container.reason}</p>
          {tracking.status ? (<div className="mt-3 text-sm"><p className="font-semibold text-ink">{tracking.status}</p><p className="text-ink-soft">{tracking.location}{tracking.vessel ? `. ${tracking.vessel}${tracking.voyage ? ` / ${tracking.voyage}` : ""}` : ""}</p>{tracking.fetched_at && <p className="text-xs text-ink-faint">Updated {timeAgo(tracking.fetched_at)}</p>}</div>)
            : <p className="mt-3 text-sm text-ink-soft">{tracking.connected ? "No tracking data yet." : "No tracking provider is connected. Update the timeline by hand."}</p>}
          {tracking.sample && <p className="mt-2 text-xs text-[#93370D]">Sample data. Not the real position of this container.</p>}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {tracking.can_refresh && tracking.connected && <Button size="sm" variant="secondary" onClick={refresh} loading={refreshing}><RefreshCw className="h-4 w-4" /> Refresh</Button>}
            <a href={tracking.search_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-sm font-semibold text-port">Look it up on the web <ExternalLink className="h-3.5 w-3.5" /></a>
          </div>
        </div>
      </div>

      <ol className="mt-6">
        {ws.timeline.map((e, i) => (
          <li key={e.key} className="relative flex gap-4 pb-5 last:pb-0">
            {i < ws.timeline.length - 1 && <span className="absolute left-[15px] top-8 h-[calc(100%-20px)] w-px bg-alice-200" />}
            <span className={cn("relative z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full", DOT[e.status])}>
              {e.status === "done" ? <Check className="h-4 w-4" /> : e.status === "blocked" ? <XOctagon className="h-4 w-4" /> : e.status === "delayed" ? <AlertTriangle className="h-4 w-4" /> : <CircleDot className="h-4 w-4" />}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className={cn("font-semibold", e.status === "pending" ? "text-ink-soft" : "text-ink")}>{e.label}</p>
                <Badge tone={e.status === "done" ? "green" : e.status === "blocked" ? "red" : e.status === "delayed" ? "amber" : e.status === "current" ? "blue" : "gray"}>{LABEL[e.status]}</Badge>
                {e.source === "tracking" && <Badge tone="blue">From tracking</Badge>}
                {e.can_update && <button onClick={() => setEditing(editing === e.key ? null : e.key)} className="text-sm font-semibold text-port hover:text-port-600">{editing === e.key ? "Cancel" : "Update"}</button>}
              </div>
              <p className="text-sm text-ink-faint">{e.actual_at ? `Done ${fmt(e.actual_at)}` : e.planned_at ? `Planned ${fmt(e.planned_at)}` : ""}{e.updated_by && e.source !== "system" ? ` by ${e.updated_by}` : ""}</p>
              {e.note && <p className="mt-1 text-sm text-[#93370D]">{e.note}</p>}
              {editing === e.key && <StepForm step={e} shipmentId={shipmentId} onDone={() => { setEditing(null); onChanged(); }} />}
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
