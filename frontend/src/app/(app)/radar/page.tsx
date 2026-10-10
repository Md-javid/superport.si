"use client";
import { Radar as RadarIcon, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { SignalCard } from "@/components/shipment/SignalCard";
import { Button } from "@/components/ui/Button";
import { Card, Skeleton } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { Signal } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function RadarPage() {
  const toast = useToast();
  const [signals, setSignals] = useState<Signal[] | null>(null);
  const [scope, setScope] = useState<"active" | "all">("active");
  const [scanning, setScanning] = useState(false);

  const load = useCallback(() => api.radarSignals(scope).then(setSignals).catch((e) => toast(e.message, "error")), [scope, toast]);
  useEffect(() => { load(); }, [load]);

  async function scan() {
    setScanning(true);
    try {
      const r = await api.radarScan();
      toast(`Scan finished: ${r.articles} articles, ${r.new} new and ${r.updated} updated signals, ${r.matched} shipment matches.${r.sample ? " (sample data)" : ""}`, "success");
      r.errors.forEach((m) => toast(m, "info"));
      await load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Scan failed.", "error");
    } finally {
      setScanning(false);
    }
  }

  async function review(id: number, action: "acknowledge" | "dismiss", note: string) {
    try { await api.radarReview(id, action, note); toast(action === "acknowledge" ? "Signal acknowledged and logged on affected shipments." : "Signal dismissed.", "success"); await load(); }
    catch (e) { toast(e instanceof Error ? e.message : "Could not save.", "error"); }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-3 font-display text-3xl font-extrabold text-prussian"><RadarIcon className="h-7 w-7 text-port" /> Trade Signal Radar</h1>
          <p className="mt-1 max-w-2xl text-ink-soft">Watches the news for port disruption, weather and rule changes that touch your active shipments. Each signal shows its sources and how well it is confirmed. Nothing here changes a shipment on its own.</p>
        </div>
        <Button onClick={scan} loading={scanning}><RefreshCw className="h-4 w-4" /> Scan now</Button>
      </div>
      <div className="flex gap-1.5 rounded-xl bg-white p-1 shadow-card ring-1 ring-alice-200 w-fit">
        {([["active", "Needs review"], ["all", "All signals"]] as const).map(([k, l]) => (
          <button key={k} onClick={() => setScope(k)} className={cn("rounded-lg px-3.5 py-1.5 text-sm font-semibold transition", scope === k ? "bg-port text-white shadow-glow" : "text-ink-soft hover:bg-port-50")}>{l}</button>
        ))}
      </div>
      {!signals && <Skeleton className="h-48" />}
      {signals?.length === 0 && <Card className="p-12 text-center"><p className="font-display text-lg font-bold text-ink">No signals right now</p><p className="mt-1 text-sm text-ink-soft">Click Scan now to search the news for your ports, routes and products.</p></Card>}
      <div className="space-y-4">{signals?.map((s) => <SignalCard key={s.id} signal={s} onReview={review} />)}</div>
    </div>
  );
}
