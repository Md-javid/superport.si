"use client";
import { PackagePlus, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { RiskBadge, StageBadge } from "@/components/shipment/StageBadge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, ProgressBar, Skeleton } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { ShipmentSummary } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "action", label: "Needs action" },
  { key: "ready", label: "Clearance ready" },
  { key: "rejected", label: "Rejected" },
];

export default function ShipmentsPage() {
  const toast = useToast();
  const [rows, setRows] = useState<ShipmentSummary[] | null>(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    api.shipments().then(setRows).catch((e) => toast(e.message, "error"));
  }, [toast]);

  const shown = useMemo(() => {
    const term = q.trim().toLowerCase();
    return (rows ?? []).filter((s) => {
      const matchesFilter = filter === "all" || (filter === "action" ? !["ready", "rejected"].includes(s.stage) : s.stage === filter);
      const hay = `${s.reference} ${s.importer} ${s.exporter} ${s.product_description} ${s.container_number}`.toLowerCase();
      return matchesFilter && (!term || hay.includes(term));
    });
  }, [rows, q, filter]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-extrabold text-prussian">Shipments</h1>
          <p className="mt-1 text-ink-soft">Every shipment, its stage, and what the copilot is waiting on.</p>
        </div>
        <Link href="/shipments/new"><Button><PackagePlus className="h-4 w-4" /> Create shipment</Button></Link>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
          <input className="field-input pl-10" placeholder="Search by ID, company, product or container" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search shipments" />
        </div>
        <div className="flex gap-1.5 rounded-xl bg-white p-1 shadow-card ring-1 ring-alice-200">
          {FILTERS.map((f) => (
            <button key={f.key} onClick={() => setFilter(f.key)} className={cn("rounded-lg px-3.5 py-1.5 text-sm font-semibold transition", filter === f.key ? "bg-port text-white shadow-glow" : "text-ink-soft hover:bg-port-50")}>{f.label}</button>
          ))}
        </div>
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="bg-alice/70 text-[13px] text-ink-faint">
              <tr>{["Shipment", "Importer", "Product", "Stage", "Progress", "Risk", "Updated"].map((h) => <th key={h} className="px-5 py-3 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {shown.map((s) => (
                <tr key={s.id} className="border-t border-alice-200/70 transition hover:bg-port-50/40">
                  <td className="px-5 py-4"><Link href={s.access === "partner" ? `/shipments/${s.id}/workspace` : `/shipments/${s.id}`} className="font-display font-bold text-ink hover:text-port">{s.reference}</Link><p className="text-[13px] text-ink-faint">{s.origin} to {s.destination}</p>{s.access === "partner" && <p className="mt-0.5"><Badge tone="blue">Shared by {s.shared_by}</Badge></p>}</td>
                  <td className="max-w-[200px] truncate px-5 py-4 text-ink-soft">{s.importer}</td>
                  <td className="max-w-[240px] truncate px-5 py-4 text-ink-soft">{s.product_description}</td>
                  <td className="px-5 py-4"><StageBadge stage={s.stage} label={s.stage_label} /></td>
                  <td className="w-40 px-5 py-4"><ProgressBar value={s.progress} color={s.stage === "ready" ? "#12B76A" : "#185DF1"} /></td>
                  <td className="px-5 py-4">{s.access === "partner" ? <span className="text-ink-faint">Not shared</span> : <RiskBadge level={s.risk_level} score={s.risk_score} />}</td>
                  <td className="px-5 py-4 text-ink-faint">{timeAgo(s.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows && <div className="p-6"><Skeleton className="h-40" /></div>}
          {rows && shown.length === 0 && <p className="p-10 text-center text-sm text-ink-soft">No shipments match. Clear the search or create a new shipment.</p>}
        </div>
      </Card>
    </div>
  );
}
