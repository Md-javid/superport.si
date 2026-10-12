"use client";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, CheckCircle2, Download, FileText, Loader2, RefreshCw, Sparkles, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { DOC_LABELS, type DocType, type ShipmentDetail } from "@/lib/types";
import { cn, formatBytes } from "@/lib/utils";
import { PIPELINE, ProcessingPipeline } from "./ProcessingPipeline";

const TYPES: { type: DocType; hint: string; sample: string }[] = [
  { type: "commercial_invoice", hint: "Seller's invoice with price and quantity", sample: "commercial_invoice.pdf" },
  { type: "packing_list", hint: "Packages, weights and container", sample: "packing_list.pdf" },
  { type: "bill_of_lading", hint: "Carrier's contract and cargo receipt", sample: "bill_of_lading.pdf" },
];
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function DocumentsStep({ shipment, onChange, onDone, readOnly }: { shipment: ShipmentDetail; onChange: (s: ShipmentDetail) => void; onDone: () => void; readOnly: boolean }) {
  const toast = useToast();
  const [uploading, setUploading] = useState<DocType | null>(null);
  const [drag, setDrag] = useState<DocType | null>(null);
  const [stage, setStage] = useState<number | null>(null);
  const [busySamples, setBusySamples] = useState(false);
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});

  const docs = Object.fromEntries(shipment.documents.map((d) => [d.doc_type, d]));
  const pending = shipment.documents.some((d) => d.status !== "ready");
  const allReady = shipment.documents.length > 0 && !pending;

  async function upload(type: DocType, file: File) {
    setUploading(type);
    try {
      onChange(await api.uploadDocument(shipment.id, type, file));
    } catch (e) {
      toast(e instanceof Error ? e.message : "Upload failed.", "error");
    } finally {
      setUploading(null);
    }
  }

  async function samples() {
    setBusySamples(true);
    try {
      onChange(await api.useSamples(shipment.id));
      toast("Sample documents attached.", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not attach samples.", "error");
    } finally {
      setBusySamples(false);
    }
  }

  async function analyze() {
    setStage(0);
    // The API call runs once; the staged animation shows the work being done.
    const request = api.process(shipment.id);
    try {
      for (let i = 0; i < PIPELINE.length - 1; i++) {
        setStage(i);
        await sleep(i === 0 ? 650 : 900);
      }
      const result = await request;
      setStage(PIPELINE.length - 1);
      onChange(result);
      await sleep(900);
      setStage(null);
      onDone();
    } catch (e) {
      setStage(null);
      toast(e instanceof Error ? e.message : "Analysis failed.", "error");
    }
  }

  return (
    <div className="space-y-5">
      <AnimatePresence>
        {stage !== null && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
            <ProcessingPipeline active={stage} />
          </motion.div>
        )}
      </AnimatePresence>

      <div>
        <h2 className="font-display text-2xl font-bold text-ink">Upload trade documents</h2>
        <p className="mt-1 text-ink-soft">Drag each file onto its card, or browse. PDFs with selectable text give the best extraction.</p>
      </div>

      {!readOnly && shipment.documents.length === 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-dashed border-port/40 bg-port-50/60 p-4">
          <Sparkles className="h-5 w-5 text-port" />
          <p className="min-w-[200px] flex-1 text-sm text-ink-soft">Attach verified sample documents for the lithium-ion battery shipment.</p>
          <Button variant="secondary" size="sm" onClick={samples} loading={busySamples}>Use sample documents</Button>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {TYPES.map(({ type, hint, sample }) => {
          const doc = docs[type];
          const isDrag = drag === type;
          return (
            <Card key={type} className={cn("relative p-5 transition", isDrag && "ring-2 ring-port shadow-glow")}>
              <div onDragOver={(e) => { e.preventDefault(); if (!readOnly) setDrag(type); }} onDragLeave={() => setDrag(null)} onDrop={(e) => { e.preventDefault(); setDrag(null); const f = e.dataTransfer.files?.[0]; if (f && !readOnly) upload(type, f); }}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-display text-[15px] font-bold text-ink">{DOC_LABELS[type]}</p>
                    <p className="text-[13px] text-ink-faint">{hint}</p>
                  </div>
                  {doc && <Badge tone={doc.status === "ready" ? "green" : "blue"} dot>{doc.status === "ready" ? "Read" : "Uploaded"}</Badge>}
                </div>

                <button type="button" disabled={readOnly} onClick={() => inputs.current[type]?.click()} className={cn("mt-4 flex h-36 w-full flex-col items-center justify-center rounded-xl border-2 border-dashed px-3 text-center transition", isDrag ? "border-port bg-port-50" : doc ? "border-signal-green/30 bg-signal-green/5" : "border-alice-200 bg-alice/60 hover:border-port-300 hover:bg-port-50/50", readOnly && "cursor-default")}>
                  {uploading === type ? (
                    <><Loader2 className="h-7 w-7 animate-spin text-port" /><span className="mt-2 text-sm font-medium text-ink-soft">Uploading...</span></>
                  ) : doc ? (
                    <><CheckCircle2 className="h-7 w-7 text-signal-green" /><span className="mt-2 flex max-w-full items-center gap-1.5 text-sm font-semibold text-ink"><FileText className="h-4 w-4 shrink-0 text-ink-faint" /><span className="truncate">{doc.filename}</span></span><span className="text-xs text-ink-faint">{formatBytes(doc.size_bytes)}{!readOnly && " · Click to replace"}</span></>
                  ) : (
                    <><motion.div animate={{ y: [0, -4, 0] }} transition={{ repeat: Infinity, duration: 2.6 }}><UploadCloud className="h-8 w-8 text-port" /></motion.div><span className="mt-2 text-sm font-semibold text-ink">Drop file here</span><span className="text-xs text-ink-faint">or click to browse</span></>
                  )}
                </button>
                <input ref={(el) => { inputs.current[type] = el; }} type="file" accept=".pdf,.png,.jpg,.jpeg,.txt" className="sr-only" aria-label={`Upload ${DOC_LABELS[type]}`} onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(type, f); e.target.value = ""; }} />
                <a href={`/api/samples/${sample}`} className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-port hover:text-port-600"><Download className="h-3.5 w-3.5" /> Download sample</a>
              </div>
            </Card>
          );
        })}
      </div>

      {!readOnly && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white p-4 shadow-card ring-1 ring-alice-200">
          <p className="text-sm text-ink-soft">
            {shipment.documents.length === 0 ? "Add at least one document to begin." : pending ? `${shipment.documents.length} of 3 documents ready for analysis.${shipment.missing_documents.length ? " Missing documents will be flagged in compliance." : ""}` : "All uploaded documents have been analysed."}
          </p>
          {allReady ? (
            <Button onClick={onDone}>Review extracted data <ArrowRight className="h-4 w-4" /></Button>
          ) : (
            <Button onClick={analyze} disabled={shipment.documents.length === 0 || stage !== null} loading={stage !== null}><RefreshCw className="h-4 w-4" /> Start AI analysis</Button>
          )}
        </div>
      )}
    </div>
  );
}
