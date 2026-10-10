"use client";
import { AnimatePresence, motion } from "framer-motion";
import { AlertOctagon, AlertTriangle, CheckCircle2, ChevronDown, CircleDot, ScrollText } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Primitives";
import type { Compliance, ComplianceItem, ItemStatus, ShipmentDetail } from "@/lib/types";
import { MarketChecksPanel } from "./MarketChecksPanel";
import { cn } from "@/lib/utils";

const STATUS: Record<ItemStatus, { icon: typeof CheckCircle2; ring: string; label: string; tone: "green" | "blue" | "amber" | "red" }> = {
  ok: { icon: CheckCircle2, ring: "bg-signal-green/10 text-signal-green", label: "Clear", tone: "green" },
  info: { icon: CircleDot, ring: "bg-port-50 text-port", label: "Awaiting review", tone: "blue" },
  warn: { icon: AlertTriangle, ring: "bg-signal-amber/10 text-signal-amber", label: "Check", tone: "amber" },
  issue: { icon: AlertOctagon, ring: "bg-signal-red/10 text-signal-red", label: "Action needed", tone: "red" },
};

function Row({ item }: { item: ComplianceItem }) {
  const [open, setOpen] = useState(item.status === "issue");
  const s = STATUS[item.status];
  const hasDetails = item.details.length > 0;
  return (
    <li>
      <button onClick={() => hasDetails && setOpen((o) => !o)} className={cn("flex w-full items-start gap-4 px-5 py-4 text-left transition", hasDetails && "hover:bg-port-50/40")} aria-expanded={open}>
        <span className={cn("mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl", s.ring)}><s.icon className="h-[18px] w-[18px]" /></span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2"><span className="font-display font-bold text-ink">{item.title}</span><Badge tone={s.tone}>{s.label}</Badge></span>
          <span className="mt-0.5 block text-sm text-ink-soft">{item.summary}</span>
        </span>
        {hasDetails && <ChevronDown className={cn("mt-1 h-4 w-4 shrink-0 text-ink-faint transition", open && "rotate-180")} />}
      </button>
      <AnimatePresence initial={false}>
        {open && hasDetails && (
          <motion.ul initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden pl-[76px] pr-5">
            {item.details.map((d) => <li key={d} className="mb-2 flex gap-2 text-sm text-ink"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-port-300" />{d}</li>)}
            <li className="h-2" />
          </motion.ul>
        )}
      </AnimatePresence>
    </li>
  );
}

export function ComplianceStep({ shipment, onChange, closed }: { shipment: ShipmentDetail; onChange: (s: ShipmentDetail) => void; closed: boolean }) {
  const compliance = shipment.compliance;
  if (!compliance) return <Card className="p-10 text-center text-ink-soft">Compliance checks run after you confirm the extracted data.</Card>;
  const banner = {
    clear: { cls: "from-signal-green/10 ring-signal-green/25 text-[#05603A]", icon: CheckCircle2 },
    needs_review: { cls: "from-signal-amber/10 ring-signal-amber/30 text-[#93370D]", icon: AlertTriangle },
    action_required: { cls: "from-signal-red/10 ring-signal-red/25 text-[#912018]", icon: AlertOctagon },
  }[compliance.overall];
  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-2xl font-bold text-ink">Compliance checks</h2>
        <p className="mt-1 text-ink-soft">What the copilot checked, what it found, and what still needs a person.</p>
      </div>
      <div className={cn("flex items-center gap-3 rounded-2xl bg-gradient-to-r to-white p-4 ring-1", banner.cls)}>
        <banner.icon className="h-5 w-5" />
        <div><p className="text-sm font-bold">Review status: {compliance.review_status}</p><p className="text-[13px] opacity-80">{compliance.alert_count} item{compliance.alert_count === 1 ? "" : "s"} need{compliance.alert_count === 1 ? "s" : ""} attention</p></div>
      </div>

      <MarketChecksPanel shipment={shipment} onChange={onChange} closed={closed} />

      <Card className="overflow-hidden"><ul className="divide-y divide-alice-200/70">{compliance.items.map((i) => <Row key={i.id} item={i} />)}</ul></Card>

      {compliance.inconsistencies.length > 0 && (
        <Card className="p-6">
          <h3 className="font-display text-base font-bold text-ink">Data inconsistencies</h3>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {compliance.inconsistencies.map((i, idx) => (
              <div key={idx} className={cn("rounded-xl border p-4", i.severity === "issue" ? "border-signal-red/25 bg-signal-red/[.04]" : "border-signal-amber/30 bg-signal-amber/[.05]")}>
                <div className="flex items-center justify-between gap-2"><p className="font-semibold text-ink">{i.field}</p><Badge tone={i.severity === "issue" ? "red" : "amber"}>{i.severity === "issue" ? "Mismatch" : "Minor difference"}</Badge></div>
                <p className="mt-1 text-sm text-ink-soft">{i.message}</p>
                <dl className="mt-3 space-y-1 text-sm">{Object.entries(i.values).map(([k, v]) => <div key={k} className="flex justify-between gap-3"><dt className="text-ink-faint">{k}</dt><dd className="text-right font-semibold text-ink">{v}</dd></div>)}</dl>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card className="p-6">
        <div className="flex items-center gap-2.5"><ScrollText className="h-5 w-5 text-port" /><h3 className="font-display text-base font-bold text-ink">Certificates usually required</h3></div>
        <ul className="mt-4 grid gap-2.5 sm:grid-cols-2">
          {compliance.certificates.map((c) => (
            <li key={c.name} className="flex items-center justify-between gap-3 rounded-xl bg-alice/70 px-4 py-3"><span className="text-sm font-medium text-ink">{c.name}{c.source ? ` [${c.source}]` : ""}</span><Badge tone="amber">{c.status}</Badge></li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-ink-faint">Basis: {compliance.rules_basis ?? compliance.rules}</p>
      </Card>
    </div>
  );
}
