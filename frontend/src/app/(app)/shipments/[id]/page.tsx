"use client";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, Clock3, Container, MapPin, Ship, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApprovalStep } from "@/components/shipment/ApprovalStep";
import { ComplianceStep } from "@/components/shipment/ComplianceStep";
import { CopilotBrief } from "@/components/shipment/CopilotBrief";
import { DocumentsStep } from "@/components/shipment/DocumentsStep";
import { ExtractionStep } from "@/components/shipment/ExtractionStep";
import { HsStep } from "@/components/shipment/HsStep";
import { RiskStep } from "@/components/shipment/RiskStep";
import { RiskBadge, StageBadge } from "@/components/shipment/StageBadge";
import { SummaryStep } from "@/components/shipment/SummaryStep";
import { WorkflowStepper } from "@/components/shipment/WorkflowStepper";
import { Badge } from "@/components/ui/Badge";
import { Card, ProgressBar, Skeleton } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { ShipmentDetail, Signal, Stage } from "@/lib/types";
import { EVENT_LABEL, verificationLabel } from "@/components/shipment/SignalCard";

// Step indexes: 0 Documents, 1 Data review, 2 HS code, 3 Compliance, 4 Risk, 5 Approval, 6 Summary
function focusFor(s: ShipmentDetail): number {
  const map: Record<Stage, number> = { draft: 0, documents: 0, extraction_review: 1, hs_review: 2, final_review: 5, ready: 6, rejected: 5 };
  return map[s.stage];
}
function maxFor(s: ShipmentDetail): number {
  switch (s.stage) {
    case "draft":
    case "documents": return s.documents.some((d) => d.status === "ready") ? 1 : 0;
    case "extraction_review": return s.hs_result ? 4 : 1;
    case "hs_review": return 4;
    case "final_review": return 5;
    default: return 6;
  }
}

export default function ShipmentPage() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  const [shipment, setShipment] = useState<ShipmentDetail | null>(null);
  const [step, setStep] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [signals, setSignals] = useState<Signal[]>([]);

  useEffect(() => {
    api.shipment(id).then((s) => { setShipment(s); setStep(focusFor(s)); }).catch((e) => { setError(e.message); toast(e.message, "error"); });
  }, [id, toast]);

  useEffect(() => { api.shipmentSignals(Number(id)).then(setSignals).catch(() => {}); }, [id]);

  const update = useCallback((s: ShipmentDetail) => setShipment(s), []);
  const go = useCallback((i: number) => { setStep(i); window.scrollTo({ top: 0, behavior: "smooth" }); }, []);

  if (error) return <Card className="p-12 text-center"><p className="font-display text-lg font-bold">Shipment not found</p><p className="mt-1 text-sm text-ink-soft">{error}</p><Link href="/shipments" className="mt-4 inline-block font-semibold text-port">Back to shipments</Link></Card>;
  if (!shipment || step === null) return <div className="space-y-4"><Skeleton className="h-32" /><Skeleton className="h-96" /></div>;

  const closed = shipment.stage === "ready" || shipment.stage === "rejected";
  const focus = focusFor(shipment);
  const max = maxFor(shipment);
  const active = Math.min(step, max);
  const after = (fn: () => void) => () => fn();

  const content = [
    <DocumentsStep key="d" shipment={shipment} onChange={update} onDone={after(() => go(1))} readOnly={closed || shipment.stage !== "documents" && shipment.stage !== "draft"} />,
    <ExtractionStep key="e" shipment={shipment} onChange={update} onConfirmed={after(() => go(2))} closed={closed} />,
    <HsStep key="h" shipment={shipment} onChange={update} onDecided={after(() => go(3))} closed={closed || shipment.stage === "extraction_review"} />,
    <ComplianceStep key="c" shipment={shipment} onChange={update} closed={closed} />,
    <RiskStep key="r" risk={shipment.risk} />,
    <ApprovalStep key="a" shipment={shipment} onChange={update} closed={closed} onDecided={(a) => go(a === "approve" ? 6 : a === "reanalyze" ? 2 : a === "edit" ? 1 : 5)} />,
    <SummaryStep key="s" shipment={shipment} />,
  ];

  return (
    <div className="space-y-6">
      <Link href="/shipments" className="no-print inline-flex items-center gap-1.5 text-sm font-semibold text-ink-soft hover:text-port"><ArrowLeft className="h-4 w-4" /> Shipments</Link>

      <motion.header initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="no-print relative overflow-hidden rounded-2xl border border-alice-200/70 bg-white p-6 shadow-card">
        <div className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-port/10 blur-3xl" />
        <div className="relative flex flex-wrap items-start justify-between gap-5">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-display text-3xl font-extrabold text-prussian">{shipment.reference}</h1>
              <StageBadge stage={shipment.stage} label={shipment.stage_label} />
              <RiskBadge level={shipment.risk_level} score={shipment.risk_score} />
            </div>
            <p className="mt-1.5 max-w-2xl text-[15px] text-ink-soft">{shipment.product_description}</p>
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1.5 text-sm text-ink-soft">
              <span className="inline-flex items-center gap-1.5"><MapPin className="h-4 w-4 text-port" />{shipment.origin} to {shipment.destination}, {shipment.port}</span>
              <span className="inline-flex items-center gap-1.5"><Ship className="h-4 w-4 text-port" />{shipment.carrier}</span>
              <span className="inline-flex items-center gap-1.5"><Container className="h-4 w-4 text-port" />{shipment.container_number}</span>
              {shipment.eta?.eta && <span className="inline-flex items-center gap-1.5 font-semibold text-ink"><Clock3 className="h-4 w-4 text-port" />ETA {new Date(shipment.eta.eta).toLocaleDateString([], { day: "numeric", month: "short" })}{shipment.eta.delay_days > 0 ? <span className="text-[#B54708]"> (+{shipment.eta.delay_days} d)</span> : null}</span>}
            </div>
          </div>
          <div className="w-full max-w-[220px]">
            <div className="flex justify-between text-xs font-semibold text-ink-soft"><span>Clearance progress</span><span>{shipment.progress}%</span></div>
            <ProgressBar value={shipment.progress} color={shipment.stage === "ready" ? "#12B76A" : "#185DF1"} className="mt-2" height={8} />
            <p className="mt-2 text-xs text-ink-faint">{shipment.importer}</p>
            <Link href={`/shipments/${shipment.id}/workspace`} className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-port-50 px-3 py-1.5 text-sm font-semibold text-port-600 hover:bg-port hover:text-white"><Users className="h-4 w-4" /> Partner workspace</Link>
          </div>
        </div>
      </motion.header>

      <div className="grid items-start gap-6 lg:grid-cols-[210px_1fr] xl:grid-cols-[210px_1fr_320px]">
        <div className="lg:sticky lg:top-8"><WorkflowStepper focus={focus} max={max} active={active} onSelect={go} /></div>
        <div className="min-w-0">
          <AnimatePresence mode="wait">
            <motion.div key={active} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.3 }}>{content[active]}</motion.div>
          </AnimatePresence>
        </div>
        <div className="lg:col-span-2 xl:sticky xl:top-8 xl:col-span-1"><CopilotBrief brief={shipment.brief} stageKey={`${shipment.stage}-${shipment.analysis_runs}`} />
          {signals.length > 0 && (
            <Card className="mt-5 p-5">
              <h3 className="font-display text-base font-bold text-ink">Signals affecting this shipment</h3>
              <ul className="mt-3 space-y-2.5">{signals.slice(0, 3).map((s) => (
                <li key={s.id} className="rounded-xl bg-alice/70 p-3 text-sm"><p className="font-semibold text-ink">{EVENT_LABEL[s.event_type] ?? "Event"}: {s.title}</p><p className="text-xs text-ink-faint">{verificationLabel(s)}, {Math.round(s.confidence * 100)}% confidence</p></li>
              ))}</ul>
              <Link href="/radar" className="mt-3 inline-block text-sm font-semibold text-port">Review on the Radar</Link>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
