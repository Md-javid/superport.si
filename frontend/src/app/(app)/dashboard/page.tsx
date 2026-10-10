"use client";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, Bot, CheckCircle2, Clock3, FileWarning, PackagePlus, ShieldAlert, Ship } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { OceanScene } from "@/components/brand/OceanScene";
import { StageBadge, RiskBadge } from "@/components/shipment/StageBadge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { AnimatedNumber, Card, ProgressBar, Ring, SectionTitle, Skeleton } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { DashboardData, Signal } from "@/lib/types";
import { EVENT_LABEL, verificationLabel } from "@/components/shipment/SignalCard";
import { greeting, timeAgo } from "@/lib/utils";

const STAGES: { key: string; label: string; color: string }[] = [
  { key: "documents", label: "Documents", color: "#8CB0FA" },
  { key: "extraction_review", label: "Data review", color: "#4F86F6" },
  { key: "hs_review", label: "HS code", color: "#185DF1" },
  { key: "final_review", label: "Awaiting approval", color: "#F79009" },
  { key: "ready", label: "Clearance ready", color: "#12B76A" },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [data, setData] = useState<DashboardData | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => toast(e.message, "error"));
  api.radarSignals().then(setSignals).catch(() => {});
  }, [toast]);

  const kpis = data?.kpis;
  const waiting = data?.attention.length ?? 0;

  return (
    <div className="space-y-8">
      {/* Command-center hero */}
      <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }} className="relative isolate overflow-hidden rounded-[28px] p-7 text-white shadow-lift sm:p-9">
        <OceanScene lanes={false} />
        <div className="relative z-10 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="max-w-xl">
            <h1 className="font-display text-3xl font-extrabold tracking-tight sm:text-[38px]">{greeting()}, {user?.name.split(" ")[0]}</h1>
            <p className="mt-3 text-[17px] leading-relaxed text-white/75">
              {data ? (waiting ? `${waiting} shipment${waiting > 1 ? "s" : ""} need your attention. SuperPort has prepared everything it can.` : "Everything is up to date. Start a new shipment when you are ready.") : "Loading your shipments..."}
            </p>
          </div>
          <Link href="/shipments/new">
            <Button variant="light" size="lg" className="shadow-[0_0_0_6px_rgba(255,255,255,.12),0_18px_50px_-10px_rgba(127,176,255,.8)]"><PackagePlus className="h-5 w-5" /> Create shipment</Button>
          </Link>
        </div>
      </motion.section>

      {/* KPIs */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {!kpis
          ? Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-36" />)
          : [
              { label: "Active shipments", value: kpis.active_shipments, icon: Ship, tint: "bg-port-50 text-port", caption: "In progress now" },
              { label: "Pending documents", value: kpis.pending_documents, icon: FileWarning, tint: "bg-signal-amber/10 text-signal-amber", caption: `Across ${kpis.pending_documents_shipments} shipment${kpis.pending_documents_shipments === 1 ? "" : "s"}` },
              { label: "Compliance alerts", value: kpis.compliance_alerts, icon: AlertTriangle, tint: "bg-signal-amber/10 text-signal-amber", caption: "Items to look at" },
              { label: "High-risk shipments", value: kpis.high_risk, icon: ShieldAlert, tint: "bg-signal-red/10 text-signal-red", caption: "Internal risk estimate" },
            ].map((k, i) => (
              <motion.div key={k.label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + i * 0.07 }}>
                <Card className="h-full p-5">
                  <div className={`grid h-10 w-10 place-items-center rounded-xl ${k.tint}`}><k.icon className="h-5 w-5" /></div>
                  <AnimatedNumber value={k.value} className="mt-4 block font-display text-4xl font-extrabold text-ink" />
                  <p className="mt-1 text-sm font-semibold text-ink">{k.label}</p>
                  <p className="text-[13px] text-ink-faint">{k.caption}</p>
                </Card>
              </motion.div>
            ))}
        {kpis && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.45 }}>
            <Card className="flex h-full items-center justify-between gap-3 p-5">
              <div>
                <p className="text-sm font-semibold text-ink">Clearance progress</p>
                <p className="mt-1 text-[13px] text-ink-faint">Average across active shipments</p>
              </div>
              <Ring value={kpis.clearance_progress} size={84}><span className="font-display text-lg font-extrabold">{kpis.clearance_progress}%</span></Ring>
            </Card>
          </motion.div>
        )}
      </section>

      {data && data.shared.length > 0 && (
        <Card className="p-6">
          <SectionTitle title="Shared with you" hint="Shipments other companies have invited you into." />
          <ul className="mt-4 grid gap-3 md:grid-cols-2">
            {data.shared.map((s) => (
              <li key={s.id}>
                <Link href={`/shipments/${s.id}/workspace`} className="flex items-center justify-between gap-3 rounded-xl bg-alice/70 p-4 transition hover:bg-port-50">
                  <div className="min-w-0"><p className="font-display font-bold text-ink">{s.reference}</p><p className="truncate text-sm text-ink-soft">{s.product_description}</p><p className="text-xs text-ink-faint">Shared by {s.shared_by} as {s.party_role}</p></div>
                  <div className="text-right">{s.open_requests > 0 ? <Badge tone="amber" dot>{s.open_requests} to provide</Badge> : <Badge tone="green" dot>Up to date</Badge>}</div>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.7fr_1fr]">
        {/* Needs attention */}
        <Card className="p-6">
          <SectionTitle title="Needs your decision" hint="Highest risk first. Each item shows what the copilot is waiting on." />
          <div className="mt-5 divide-y divide-alice-200/70">
            {!data && <Skeleton className="h-40" />}
            {data?.attention.length === 0 && <p className="py-8 text-center text-sm text-ink-soft">Nothing is waiting on you.</p>}
            {data?.attention.map((s) => (
              <Link key={s.id} href={`/shipments/${s.id}`} className="group flex flex-wrap items-center gap-x-5 gap-y-2 py-4 first:pt-0 last:pb-0">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2.5">
                    <span className="font-display font-bold text-ink">{s.reference}</span>
                    <RiskBadge level={s.risk_level} score={s.risk_score} />
                  </div>
                  <p className="mt-0.5 truncate text-sm text-ink-soft">{s.product_description}</p>
                  <p className="text-[13px] text-ink-faint">{s.origin} to {s.destination} via {s.port}</p>
                </div>
                <span className="inline-flex items-center gap-1.5 rounded-xl bg-port-50 px-3.5 py-2 text-sm font-semibold text-port-600 transition group-hover:bg-port group-hover:text-white">
                  {s.action} <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
                </span>
              </Link>
            ))}
          </div>
        </Card>

        <div className="space-y-6">
          <Card className="p-6">
            <SectionTitle title="Trade Signal Radar" hint="News that may touch your shipments." action={<Link href="/radar" className="text-sm font-semibold text-port hover:text-port-600">Open</Link>} />
            <ul className="mt-4 space-y-3">
              {signals.slice(0, 3).map((s) => (
                <li key={s.id}>
                  <Link href="/radar" className="block rounded-xl bg-alice/70 p-3 transition hover:bg-port-50">
                    <div className="flex items-center justify-between gap-2"><Badge tone={s.severity === "high" ? "red" : s.severity === "medium" ? "amber" : "gray"} dot>{EVENT_LABEL[s.event_type] ?? "Event"}</Badge><span className="text-xs font-semibold text-ink-faint">{Math.round(s.confidence * 100)}%</span></div>
                    <p className="mt-1.5 text-sm font-semibold text-ink">{s.title}</p>
                    <p className="text-xs text-ink-faint">{verificationLabel(s)}{s.affected.length ? `. Affects ${s.affected.length} shipment${s.affected.length > 1 ? "s" : ""}` : ""}</p>
                  </Link>
                </li>
              ))}
              {signals.length === 0 && <li className="text-sm text-ink-soft">No open signals. Open the Radar and click Scan now.</li>}
            </ul>
          </Card>

          <Card className="p-6">
            <SectionTitle title="Where shipments are" />
            <div className="mt-5 flex h-3 overflow-hidden rounded-full bg-alice-200/70">
              {STAGES.map((s) => {
                const n = data?.stage_counts[s.key] ?? 0;
                return n ? <motion.div key={s.key} initial={{ flexGrow: 0 }} animate={{ flexGrow: n }} transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }} style={{ background: s.color }} className="h-full border-r-2 border-white last:border-0" title={`${s.label}: ${n}`} /> : null;
              })}
            </div>
            <ul className="mt-5 space-y-2.5">
              {STAGES.map((s) => (
                <li key={s.key} className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2.5 text-ink-soft"><span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />{s.label}</span>
                  <span className="font-semibold text-ink">{data?.stage_counts[s.key] ?? 0}</span>
                </li>
              ))}
            </ul>
          </Card>

          {data?.intelligence && (
            <Card className="p-6">
              <SectionTitle title="Intelligence layer" hint={data.intelligence.note} />
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge tone={data.intelligence.mode === "live" ? "green" : data.intelligence.mode === "fixtures" ? "amber" : "gray"} dot>Mode: {data.intelligence.mode}</Badge>
                <Badge tone={data.intelligence.gemini.configured ? "green" : "gray"}>Gemini {data.intelligence.gemini.configured ? "key set" : "no key"}</Badge>
                <Badge tone={data.intelligence.serpapi.configured ? "green" : "gray"}>SerpApi {data.intelligence.serpapi.configured ? "key set" : "no key"}</Badge>
              </div>
              {data.intelligence.mode === "live" && (
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-xl bg-alice/70 p-3"><dt className="text-ink-faint">Searches (30 days)</dt><dd className="font-display text-lg font-bold text-ink">{data.intelligence.usage_30d.serpapi.live_calls}<span className="ml-1 text-xs font-medium text-ink-faint">+{data.intelligence.usage_30d.serpapi.cache_hits} cached</span></dd></div>
                  <div className="rounded-xl bg-alice/70 p-3"><dt className="text-ink-faint">Gemini calls</dt><dd className="font-display text-lg font-bold text-ink">{data.intelligence.usage_30d.gemini.live_calls}<span className="ml-1 text-xs font-medium text-ink-faint">+{data.intelligence.usage_30d.gemini.cache_hits} cached</span></dd></div>
                </dl>
              )}
              {data.intelligence.warnings.map((w) => <p key={w} className="mt-3 rounded-xl bg-signal-amber/10 px-3 py-2 text-[13px] font-medium text-[#93370D]">{w}</p>)}
            </Card>
          )}

          <Card className="p-6">
            <SectionTitle title="Copilot agents" hint="Phase 1 runs four agents. More plug in later." />
            <ul className="mt-4 space-y-3">
              {data?.agents.map((a) => (
                <li key={a.name} className="flex items-start gap-3">
                  <span className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg ${a.status === "active" ? "bg-port-50 text-port" : "bg-alice-100 text-ink-faint"}`}><Bot className="h-4 w-4" /></span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-ink">{a.title}</p>
                      <Badge tone={a.status === "active" ? "green" : "gray"}>{a.status === "active" ? "Active" : "Planned"}</Badge>
                    </div>
                    <p className="text-[13px] leading-snug text-ink-soft">{a.description}</p>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>

      {/* Recent */}
      <Card className="overflow-hidden">
        <div className="p-6 pb-3"><SectionTitle title="Recent shipments" action={<Link href="/shipments" className="text-sm font-semibold text-port hover:text-port-600">View all</Link>} /></div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="text-[13px] text-ink-faint">
              <tr>{["Shipment", "Route", "Stage", "Progress", "Risk", "Updated"].map((h) => <th key={h} className="px-6 py-3 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {data?.recent.map((s) => (
                <tr key={s.id} className="border-t border-alice-200/70 transition hover:bg-port-50/40">
                  <td className="px-6 py-4"><Link href={`/shipments/${s.id}`} className="font-display font-bold text-ink hover:text-port">{s.reference}</Link><p className="max-w-[240px] truncate text-[13px] text-ink-faint">{s.product_description}</p></td>
                  <td className="px-6 py-4 text-ink-soft">{s.origin} to {s.destination}</td>
                  <td className="px-6 py-4"><StageBadge stage={s.stage} label={s.stage_label} /></td>
                  <td className="w-44 px-6 py-4"><div className="flex items-center gap-3"><ProgressBar value={s.progress} color={s.stage === "ready" ? "#12B76A" : "#185DF1"} className="flex-1" /><span className="w-9 text-xs font-semibold text-ink-soft">{s.progress}%</span></div></td>
                  <td className="px-6 py-4"><RiskBadge level={s.risk_level} score={s.risk_score} /></td>
                  <td className="px-6 py-4 text-ink-faint"><span className="inline-flex items-center gap-1.5"><Clock3 className="h-3.5 w-3.5" />{timeAgo(s.updated_at)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!data && <div className="p-6"><Skeleton className="h-32" /></div>}
        </div>
      </Card>
      {data && <p className="flex items-center gap-2 text-xs text-ink-faint"><CheckCircle2 className="h-3.5 w-3.5" /> {data.ai.note}</p>}
    </div>
  );
}
