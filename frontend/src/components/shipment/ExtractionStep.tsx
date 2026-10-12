"use client";
import { AlertTriangle, ArrowRight, CheckCircle2, Info, Pencil, Wand2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, ProgressBar } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { DocumentOut, ExtractedField, ShipmentDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

const SOURCE: Record<ExtractedField["source"], { label: string; tone: "green" | "blue" | "amber" | "red" | "gray" }> = {
  extracted: { label: "Read from file", tone: "green" },
  "gemini-vision": { label: "Read by Gemini", tone: "blue" },
  "demo-synthesized": { label: "Estimated", tone: "amber" },
  edited: { label: "Edited by you", tone: "blue" },
  "not-found": { label: "Not found", tone: "red" },
};

function FieldRow({ field, disabled, onSave }: { field: ExtractedField; disabled: boolean; onSave: (value: string) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(field.value);
  const [saving, setSaving] = useState(false);
  const lowConf = field.value && field.confidence < 0.85;

  async function commit() {
    setEditing(false);
    if (value.trim() === field.value) return;
    setSaving(true);
    try {
      await onSave(value);
    } catch {
      setValue(field.value);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={cn("grid items-center gap-x-4 gap-y-1 px-5 py-3.5 sm:grid-cols-[170px_1fr_150px_130px]", lowConf && "bg-signal-amber/[.04]")}>
      <p className="text-sm font-medium text-ink-soft">{field.label}</p>
      <div className="min-w-0">
        {editing ? (
          <input autoFocus className="field-input !py-2" value={value} onChange={(e) => setValue(e.target.value)} onBlur={commit} onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") { setValue(field.value); setEditing(false); } }} aria-label={`Edit ${field.label}`} />
        ) : (
          <button disabled={disabled} onClick={() => { setValue(field.value); setEditing(true); }} className="group flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition hover:bg-port-50 disabled:hover:bg-transparent" aria-label={`Edit ${field.label}`}>
            <span className={cn("min-w-0 flex-1 break-words text-[15px]", field.value ? "font-semibold text-ink" : "italic text-ink-faint")}>{saving ? "Saving..." : field.value || "Empty. Click to add"}</span>
            {!disabled && <Pencil className="h-3.5 w-3.5 shrink-0 text-ink-faint opacity-0 transition group-hover:opacity-100" />}
          </button>
        )}
        {field.edited && field.original && <p className="px-2 text-xs text-ink-faint">Originally: {field.original}</p>}
      </div>
      <div className="flex items-center gap-2.5">
        {field.value && field.source !== "edited" ? (
          <>
            <ProgressBar value={field.confidence * 100} color={lowConf ? "#F79009" : "#12B76A"} className="w-16" />
            <span className={cn("text-xs font-semibold", lowConf ? "text-[#B54708]" : "text-ink-soft")}>{Math.round(field.confidence * 100)}%</span>
          </>
        ) : null}
      </div>
      <Badge tone={SOURCE[field.source].tone}>{SOURCE[field.source].label}</Badge>
    </div>
  );
}

const MATRIX: { key: string; label: string; kind: "id" | "num" | "text" }[] = [
  { key: "container_number", label: "Container number", kind: "id" },
  { key: "gross_weight", label: "Gross weight", kind: "num" },
  { key: "quantity", label: "Quantity", kind: "num" },
  { key: "consignee", label: "Consignee", kind: "text" },
  { key: "shipper", label: "Shipper", kind: "text" },
];
const normalise = (v: string, kind: "id" | "num" | "text") =>
  kind === "num" ? (v.match(/-?\d[\d,]*\.?\d*/)?.[0] ?? v).replace(/,/g, "") : v.toLowerCase().replace(/[^a-z0-9]/g, "");

function CrossCheck({ docs }: { docs: DocumentOut[] }) {
  const cols = ["commercial_invoice", "packing_list", "bill_of_lading"] as const;
  const get = (type: string, key: string) => docs.find((d) => d.doc_type === type)?.fields.find((f) => f.key === key)?.value ?? "";
  return (
    <Card className="overflow-hidden">
      <div className="p-5 pb-3">
        <h3 className="font-display text-base font-bold text-ink">Cross-check across documents</h3>
        <p className="text-sm text-ink-soft">Values that should agree between documents. Differences are highlighted.</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="text-left text-[13px] text-ink-faint"><tr><th className="px-5 py-2 font-medium">Field</th><th className="px-3 py-2 font-medium">Invoice</th><th className="px-3 py-2 font-medium">Packing list</th><th className="px-3 py-2 font-medium">Bill of lading</th><th className="px-5 py-2 font-medium">Result</th></tr></thead>
          <tbody>
            {MATRIX.map((m) => {
              const vals = cols.map((c) => get(c, m.key));
              const present = vals.filter(Boolean).map((v) => normalise(v, m.kind));
              const mismatch = new Set(present).size > 1;
              return (
                <tr key={m.key} className="border-t border-alice-200/70">
                  <td className="px-5 py-3 font-medium text-ink-soft">{m.label}</td>
                  {vals.map((v, i) => <td key={i} className={cn("px-3 py-3", mismatch ? "font-semibold text-[#B54708]" : "text-ink")}>{v || <span className="text-ink-faint">Not on document</span>}</td>)}
                  <td className="px-5 py-3">{present.length < 2 ? <Badge>Not enough data</Badge> : mismatch ? <Badge tone="amber" dot>Differs</Badge> : <Badge tone="green" dot>Match</Badge>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function ExtractionStep({ shipment, onChange, onConfirmed, closed }: { shipment: ShipmentDetail; onChange: (s: ShipmentDetail) => void; onConfirmed: () => void; closed: boolean }) {
  const toast = useToast();
  const ready = shipment.documents.filter((d) => d.status === "ready");
  const [tab, setTab] = useState(0);
  const [busy, setBusy] = useState(false);
  const doc = ready[Math.min(tab, ready.length - 1)];
  const hasEstimatedFields = ready.some((d) => d.fields.some((f) => f.source === "demo-synthesized"));
  const canConfirm = shipment.stage === "extraction_review";
  const lowCount = ready.reduce((n, d) => n + d.fields.filter((f) => f.value && f.confidence < 0.85).length, 0);

  async function confirm() {
    setBusy(true);
    try {
      onChange(await api.confirmExtraction(shipment.id));
      toast("Data confirmed. HS code suggestion is ready for review.", "success");
      onConfirmed();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not confirm.", "error");
    } finally {
      setBusy(false);
    }
  }

  const unreadable = ready.filter((d) => d.meta?.mode === "unreadable");
  if (!doc) return <Card className="p-10 text-center"><p className="font-semibold text-ink">No documents have been analysed yet.</p><p className="mt-1 text-sm text-ink-soft">Go back to Documents and start the AI analysis.</p></Card>;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-2xl font-bold text-ink">Review extracted data</h2>
        <p className="mt-1 text-ink-soft">Click any value to correct it. Lower-confidence values are highlighted so you know where to look first.</p>
      </div>

      {unreadable.length > 0 && (
        <div className="flex gap-3 rounded-2xl border border-signal-red/25 bg-signal-red/[.05] p-4 text-sm text-[#912018]">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div><p className="font-semibold">Could not read {unreadable.map((d) => d.label).join(", ")}.</p><p className="mt-0.5">{String(unreadable[0].meta?.error ?? "")} Type the values in by hand, or upload a clearer file.</p></div>
        </div>
      )}
      {ready.some((d) => d.meta?.mode === "gemini-vision") && (
        <div className="flex gap-3 rounded-2xl border border-port/20 bg-port-50/70 p-4 text-sm text-prussian-700">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-port" />
          <p>Some documents were read by Gemini. Confidence is capped below 100% and values missing from the file&apos;s own text are marked lower. Please check the numbers.</p>
        </div>
      )}
      {hasEstimatedFields && (
        <div className="flex gap-3 rounded-2xl border border-signal-amber/30 bg-signal-amber/[.07] p-4 text-sm text-[#7A2E0E]">
          <Info className="mt-0.5 h-4 w-4 shrink-0" />
          <p>Some values were estimated because the uploaded file had unreadable sections. Verify line items before confirming.</p>
        </div>
      )}
      {canConfirm && lowCount > 0 && (
        <div className="flex gap-3 rounded-2xl border border-port/20 bg-port-50/70 p-4 text-sm text-prussian-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-port" />
          <p>{lowCount} value{lowCount > 1 ? "s have" : " has"} lower confidence. Check {lowCount > 1 ? "them" : "it"} before confirming.</p>
        </div>
      )}
      {!canConfirm && !closed && (
        <div className="flex gap-3 rounded-2xl border border-alice-200 bg-white p-4 text-sm text-ink-soft">
          <Wand2 className="mt-0.5 h-4 w-4 shrink-0 text-port" />
          <p>Edits made now refresh the HS suggestion, compliance checks and risk score automatically.</p>
        </div>
      )}

      <div className="flex gap-1.5 overflow-x-auto rounded-xl bg-white p-1 shadow-card ring-1 ring-alice-200" role="tablist">
        {ready.map((d, i) => (
          <button key={d.id} role="tab" aria-selected={i === tab} onClick={() => setTab(i)} className={cn("whitespace-nowrap rounded-lg px-4 py-2 text-sm font-semibold transition", i === tab ? "bg-port text-white shadow-glow" : "text-ink-soft hover:bg-port-50")}>{d.label}</button>
        ))}
      </div>

      <Card className="overflow-hidden">
        <div className="hidden gap-4 border-b border-alice-200/70 bg-alice/70 px-5 py-2.5 text-[13px] font-medium text-ink-faint sm:grid sm:grid-cols-[170px_1fr_150px_130px]"><span>Field</span><span className="pl-2">Value</span><span>Confidence</span><span>Source</span></div>
        <div className="divide-y divide-alice-200/60">
          {doc.fields.map((f) => (
            <FieldRow key={`${doc.id}-${f.key}-${f.value}`} field={f} disabled={closed} onSave={async (v) => {
              try { onChange(await api.editField(shipment.id, doc.id, f.key, v)); toast(`${f.label} updated.`, "success"); } catch (e) { toast(e instanceof Error ? e.message : "Could not save.", "error"); throw e; }
            }} />
          ))}
        </div>
      </Card>

      <CrossCheck docs={ready} />

      {canConfirm && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white p-4 shadow-card ring-1 ring-alice-200">
          <p className="flex items-center gap-2 text-sm text-ink-soft"><CheckCircle2 className="h-4 w-4 text-port" /> Confirming tells SuperPort the data is correct to the best of your knowledge.</p>
          <Button onClick={confirm} loading={busy}>Confirm data and classify <ArrowRight className="h-4 w-4" /></Button>
        </div>
      )}
    </div>
  );
}
