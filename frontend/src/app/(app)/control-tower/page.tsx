"use client";
import { motion } from "framer-motion";
import { AlertOctagon, CheckCircle2, Clock3, FileWarning, ShieldAlert, Waves } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Card, Skeleton } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { ControlTower, TowerCategory } from "@/lib/types";
import { cn } from "@/lib/utils";

const TILES: { key: TowerCategory; icon: typeof AlertOctagon; ring: string; text: string }[] = [
  { key: "customs_hold", icon: AlertOctagon, ring: "ring-signal-red/30 bg-signal-red/[.06]", text: "text-[#B42318]" },
  { key: "port_event", icon: Waves, ring: "ring-signal-red/30 bg-signal-red/[.06]", text: "text-[#B42318]" },
  { key: "needs_review", icon: ShieldAlert, ring: "ring-signal-red/30 bg-signal-red/[.06]", text: "text-[#B42318]" },
  { key: "vessel_delay", icon: Clock3, ring: "ring-signal-amber/35 bg-signal-amber/[.08]", text: "text-[#B54708]" },
  { key: "missing_document", icon: FileWarning, ring: "ring-signal-amber/35 bg-signal-amber/[.08]", text: "text-[#B54708]" },
  { key: "cleared", icon: CheckCircle2, ring: "ring-signal-green/30 bg-signal-green/[.07]", text: "text-[#067647]" },
];
const TONE: Record<string, Tone> = { red: "red", amber: "amber", green: "green" };

export default function ControlTowerPage() {
  const toast = useToast();
  const [data, setData] = useState<ControlTower | null>(null);
  const [filter, setFilter] = useState<TowerCategory | "all">("all");
  useEffect(() => { api.controlTower().then(setData).catch((e) => toast(e.message, "error")); }, [toast]);

  const rows = useMemo(() => (data?.shipments ?? []).filter((r) => (filter === "all" ? !r.on_track || r.exceptions.length > 0 : r.exceptions.some((e) => e.category === filter))), [data, filter]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-extrabold text-prussian">Control Tower</h1>
        <p className="mt-1 max-w-2xl text-ink-soft">Most shipments are boring. This board shows only the ones that need attention, worst first.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {!data ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-24" />) : TILES.map((t, i) => (
          <motion.button key={t.key} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} onClick={() => setFilter(filter === t.key ? "all" : t.key)}
            className={cn("rounded-2xl p-4 text-left ring-1 transition hover:shadow-lift", t.ring, filter === t.key && "outline outline-2 outline-port")}>
            <t.icon className={cn("h-5 w-5", t.text)} />
            <p className={cn("mt-2 font-display text-3xl font-extrabold", t.text)}>{data.counts[t.key]}</p>
            <p className="text-sm font-semibold text-ink">{data.labels[t.key]}</p>
          </motion.button>
        ))}
      </div>
      {filter !== "all" && <p className="text-sm text-ink-soft">Showing {data?.labels[filter]}. <button className="font-semibold text-port" onClick={() => setFilter("all")}>Show all exceptions</button></p>}
      {!data && <Skeleton className="h-48" />}
      {data && rows.length === 0 && <Card className="p-12 text-center"><CheckCircle2 className="mx-auto h-8 w-8 text-signal-green" /><p className="mt-3 font-display text-lg font-bold text-ink">Nothing needs attention</p><p className="mt-1 text-sm text-ink-soft">All {data.total} shipments are on track.</p></Card>}
      <div className="space-y-3">
        {rows.map((r) => (
          <Card key={r.id} className="p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2.5">
                  <Link href={r.link} className="font-display text-lg font-bold text-ink hover:text-port">{r.reference}</Link>
                  <Badge tone={TONE[r.severity]} dot>{r.severity === "red" ? "Act now" : r.severity === "amber" ? "Watch" : "Clear"}</Badge>
                  {r.access === "partner" && <Badge tone="blue">Shared, you are the {r.party_role}</Badge>}
                </div>
                <p className="mt-0.5 truncate text-sm text-ink-soft">{r.product}</p>
                <p className="text-xs text-ink-faint">{r.route} via {r.port}{r.eta ? `, ETA ${new Date(r.eta).toLocaleDateString([], { day: "numeric", month: "short" })}` : ""}</p>
              </div>
              <Link href={r.workspace_link} className="text-sm font-semibold text-port hover:text-port-600">Open workspace</Link>
            </div>
            <ul className="mt-3 grid gap-2 md:grid-cols-2">
              {r.exceptions.map((e, i) => (
                <li key={i} className="flex items-start gap-2.5 rounded-xl bg-alice/70 px-3.5 py-2.5 text-sm"><Badge tone={TONE[e.severity]}>{data?.labels[e.category]}</Badge><div><p className="font-semibold text-ink">{e.title}</p><p className="text-[13px] text-ink-soft">{e.detail}</p></div></li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </div>
  );
}
