"use client";
import { motion } from "framer-motion";
import { Globe2, MapPin, Newspaper, Search, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { AnimatedNumber, Card, Skeleton } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { IntelligenceStatus, SerpApiShowcase } from "@/lib/types";

const ICON: Record<string, typeof Search> = { google: Search, google_shopping: ShoppingCart, google_maps: MapPin, google_news: Newspaper };
const STORY = [
  { n: "1", title: "Global Sensing", text: "The Horizon Grid transforms live web queries into clean, structured trade signals: verified product listings, commodity prices, company registries, and port advisories." },
  { n: "2", title: "Ground Truth", text: "Every observation is anchored with its URL, timestamp, and source trust classification (official gazette, regulatory reference, verified counterparty). Nothing is asserted without evidence." },
  { n: "3", title: "Cognitive Synthesis", text: "Gemini synthesizes the live evidence to determine compliance findings and anomaly flags. Uncited claims or hallucinations are automatically discarded." },
  { n: "4", title: "Human Authority", text: "Licensed brokers and trade operators maintain full decision authority. External signals provide situational clarity, never blind automation." },
];

export default function SerpApiPage() {
  const toast = useToast();
  const [data, setData] = useState<SerpApiShowcase | null>(null);
  const [status, setStatus] = useState<IntelligenceStatus | null>(null);
  useEffect(() => { api.serpapiShowcase().then(setData).catch((e) => toast(e.message, "error")); api.intelligence().then(setStatus).catch(() => {}); }, [toast]);
  const total = data?.features.reduce((n, f) => n + f.searches + f.cached, 0) ?? 0;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-3 font-display text-3xl font-extrabold text-prussian"><Globe2 className="h-7 w-7 text-port" /> Horizon Sensory Grid</h1>
        <p className="mt-1 max-w-3xl text-ink-soft">Global trade decisions demand facts anchored in the live real world: regulatory tariff schedules, cross-border market prices, counterparty registries, and maritime port advisories. The Horizon Sensory Grid continuously transforms open-web telemetry into structured, clickable evidence.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-4">{STORY.map((s, i) => (
        <motion.div key={s.n} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }} className="surface p-5">
          <span className="grid h-8 w-8 place-items-center rounded-full brand-gradient text-sm font-bold text-white">{s.n}</span><p className="mt-3 font-display font-bold text-ink">{s.title}</p><p className="mt-1 text-[13px] leading-snug text-ink-soft">{s.text}</p></motion.div>))}</div>

      <div className="flex flex-wrap items-center gap-3">
        <Badge tone={status?.mode === "live" ? "green" : status?.mode === "fixtures" ? "amber" : "gray"} dot>Mode: {status?.mode ?? "..."}</Badge>
        <Badge tone={status?.serpapi.configured ? "green" : "gray"}>Sensory Mesh: {status?.serpapi.configured ? "Online" : "Offline"}</Badge>
        {status?.mode !== "live" && <span className="text-sm text-ink-soft">Counts below are zero until live mode is on. Fixtures mode shows labelled sample data.</span>}
      </div>

      {!data ? <Skeleton className="h-64" /> : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            {data.features.map((f, i) => { const Icon = ICON[f.engine] ?? Search; return (
              <motion.div key={f.engine} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.07 }}>
                <Card className="h-full p-6">
                  <div className="flex items-start justify-between gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-port-50 text-port"><Icon className="h-5 w-5" /></span>
                    <div className="text-right"><p className="font-display text-3xl font-extrabold text-ink"><AnimatedNumber value={f.searches} /></p><p className="text-xs text-ink-faint">live telemetry queries, +{f.cached} from cache (30 days)</p></div></div>
                  <h3 className="mt-3 font-display text-lg font-bold text-ink">{f.name}</h3><p className="mt-1 text-sm text-ink-soft">{f.what}</p><p className="mt-2 text-xs font-semibold text-port-600">Used in: {f.where}</p>
                </Card>
              </motion.div>); })}
          </div>
          <Card className="p-6">
            <h3 className="font-display text-base font-bold text-ink">Live Telemetry Evidence Produced for Your Operations</h3>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl bg-alice/70 p-4"><p className="font-display text-3xl font-extrabold text-ink"><AnimatedNumber value={data.evidence_total} /></p><p className="text-sm text-ink-soft">sourced evidence links saved</p></div>
              <div className="rounded-xl bg-alice/70 p-4"><p className="font-display text-3xl font-extrabold text-ink"><AnimatedNumber value={data.signals} /></p><p className="text-sm text-ink-soft">disruption signals on Radar</p></div>
              <div className="rounded-xl bg-alice/70 p-4"><p className="font-display text-3xl font-extrabold text-ink"><AnimatedNumber value={total} /></p><p className="text-sm text-ink-soft">telemetry queries in 30 days (cache included)</p></div>
            </div>
            <p className="mt-4 text-sm text-ink-soft">Cost control: results are cached, each shipment has a search budget, and the whole app has a daily cap. See the evidence on the <Link href="/shipments" className="font-semibold text-port">HS code</Link>, <Link href="/shipments" className="font-semibold text-port">Compliance</Link> and <Link href="/radar" className="font-semibold text-port">Radar</Link> screens.</p>
            <div className="mt-4 flex flex-wrap items-center justify-between border-t border-alice-200/60 pt-3 text-xs text-ink-faint">
              <span>Automated caching & per-shipment query budgets enabled.</span>
              <span className="font-medium text-ink-soft">Search telemetry engine orchestrated via SerpApi multi-engine cluster</span>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
