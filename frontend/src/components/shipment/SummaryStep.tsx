"use client";
import { CheckCircle2, Lock, Printer } from "lucide-react";
import { useEffect, useState } from "react";
import { Logo } from "@/components/brand/Logo";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, Skeleton } from "@/components/ui/Primitives";
import { api } from "@/lib/api";
import type { ClearanceSummary, ShipmentDetail } from "@/lib/types";

const Row = ({ k, v }: { k: string; v?: string | null }) => (
  <div className="flex justify-between gap-6 border-b border-alice-200/70 py-2.5 text-sm last:border-0"><dt className="text-ink-soft">{k}</dt><dd className="text-right font-semibold text-ink">{v || "Not provided"}</dd></div>
);

export function SummaryStep({ shipment }: { shipment: ShipmentDetail }) {
  const [data, setData] = useState<ClearanceSummary | null>(null);
  useEffect(() => {
    if (shipment.stage === "ready") api.summary(shipment.id).then(setData).catch(() => {});
  }, [shipment.id, shipment.stage]);

  if (shipment.stage !== "ready")
    return <Card className="p-12 text-center"><Lock className="mx-auto h-8 w-8 text-ink-faint" /><p className="mt-3 font-display text-lg font-bold text-ink">Summary unlocks after approval</p><p className="mt-1 text-sm text-ink-soft">Once you approve the shipment, a clearance-ready summary is generated here.</p></Card>;
  if (!data) return <Skeleton className="h-96" />;

  const g = data.goods;
  return (
    <div className="space-y-5">
      <div className="no-print flex flex-wrap items-end justify-between gap-3">
        <div><h2 className="font-display text-2xl font-bold text-ink">Clearance-ready summary</h2><p className="mt-1 text-ink-soft">Everything your submission team needs, in one place.</p></div>
        <Button variant="secondary" onClick={() => window.print()}><Printer className="h-4 w-4" /> Print or save as PDF</Button>
      </div>
      <Card className="print-area overflow-hidden">
        <div className="relative overflow-hidden bg-gradient-to-br from-prussian via-prussian-700 to-port p-7 text-white">
          <div className="absolute -right-10 -top-16 h-56 w-56 rounded-full bg-port-300/40 blur-3xl animate-aurora" />
          <div className="relative flex flex-wrap items-center justify-between gap-4">
            <div><Logo dark /><p className="mt-4 font-display text-2xl font-extrabold">{data.reference}</p><p className="text-sm text-white/70">{data.route.origin} to {data.route.destination} via {data.route.port}</p></div>
            <span className="inline-flex items-center gap-2 rounded-full bg-signal-green px-4 py-2 text-sm font-bold"><CheckCircle2 className="h-4 w-4" /> {data.status_label}</span>
          </div>
        </div>
        <div className="grid gap-x-10 gap-y-6 p-7 md:grid-cols-2">
          <section><h3 className="font-display text-base font-bold text-ink">Parties and route</h3><dl className="mt-2"><Row k="Importer" v={data.parties.importer} /><Row k="Exporter" v={data.parties.exporter} /><Row k="Carrier" v={data.route.carrier} /><Row k="Container" v={data.route.container} /><Row k="Vessel and voyage" v={data.route.vessel} /></dl></section>
          <section><h3 className="font-display text-base font-bold text-ink">Goods and value</h3><dl className="mt-2"><Row k="Description" v={g.description} /><Row k="Quantity" v={g.quantity} /><Row k="Unit price" v={g.unit_price && `${g.currency ?? ""} ${g.unit_price}`} /><Row k="Total value" v={g.total_value && `${g.currency ?? ""} ${g.total_value}`} /><Row k="Gross weight" v={g.gross_weight} /><Row k="Country of origin" v={g.country_of_origin} /></dl></section>
          <section><h3 className="font-display text-base font-bold text-ink">Classification</h3><dl className="mt-2"><Row k="Approved HS code" v={data.hs.code} /><Row k="Decision" v={data.hs.decision === "edited" ? "Changed by reviewer" : "AI suggestion approved"} /><Row k="AI suggestion" v={data.hs.ai_code && `${data.hs.ai_code} (${Math.round((data.hs.confidence ?? 0) * 100)}% confidence)`} /></dl></section>
          <section><h3 className="font-display text-base font-bold text-ink">Compliance and risk</h3><dl className="mt-2"><Row k="Compliance status" v={data.compliance.review_status} /><Row k="Internal risk score" v={data.risk.score != null ? `${data.risk.score} / 100, ${data.risk.label}` : null} /></dl></section>
          {data.compliance.open_items.length > 0 && <section className="md:col-span-2"><h3 className="font-display text-base font-bold text-ink">Items to carry into submission</h3><ul className="mt-2 space-y-1.5">{data.compliance.open_items.map((i) => <li key={i} className="text-sm text-ink-soft">{i}</li>)}</ul></section>}
          <section className="md:col-span-2"><h3 className="font-display text-base font-bold text-ink">Approvals</h3><ul className="mt-3 space-y-2">{data.approvals.map((a) => <li key={a.id} className="flex flex-wrap items-center gap-2 text-sm"><Badge tone="navy">{a.actor}</Badge><span className="text-ink">{a.message}</span><span className="text-xs text-ink-faint">{new Date(a.created_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</span></li>)}</ul></section>
        </div>
        <p className="border-t border-alice-200 bg-alice/60 px-7 py-4 text-xs leading-relaxed text-ink-soft">{data.disclaimer}</p>
      </Card>
    </div>
  );
}
