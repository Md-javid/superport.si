"use client";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Pencil,
  Play,
  RotateCcw,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { Compliance, ComplianceItem, Inconsistency, ItemStatus, ShipmentDetail } from "@/lib/types";
import { MarketChecksPanel } from "./MarketChecksPanel";
import { cn } from "@/lib/utils";

const STATUS: Record<ItemStatus, { icon: typeof CheckCircle2; ring: string; label: string; tone: "green" | "blue" | "amber" | "red" }> = {
  ok: { icon: CheckCircle2, ring: "bg-signal-green/10 text-signal-green", label: "Clear", tone: "green" },
  info: { icon: CircleDot, ring: "bg-port-50 text-port", label: "Awaiting review", tone: "blue" },
  warn: { icon: AlertTriangle, ring: "bg-signal-amber/10 text-signal-amber", label: "Check", tone: "amber" },
  issue: { icon: AlertOctagon, ring: "bg-signal-red/10 text-signal-red", label: "Action needed", tone: "red" },
};

function Row({
  item,
  onRunMarketChecks,
  busyMarketChecks,
}: {
  item: ComplianceItem;
  onRunMarketChecks?: () => void;
  busyMarketChecks?: boolean;
}) {
  const [open, setOpen] = useState(item.status === "issue");
  const s = STATUS[item.status];
  const hasDetails = item.details.length > 0;
  const isCounterparty = item.id === "counterparties";
  const needsMarketCheck = isCounterparty && item.status !== "ok";

  return (
    <li>
      <div className={cn("flex w-full items-start gap-4 px-5 py-4 text-left transition", hasDetails && "hover:bg-port-50/40")}>
        <span className={cn("mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl", s.ring)}>
          <s.icon className="h-[18px] w-[18px]" />
        </span>
        <div className="min-w-0 flex-1 cursor-pointer" onClick={() => hasDetails && setOpen((o) => !o)}>
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-display font-bold text-ink">{item.title}</span>
            <Badge tone={s.tone}>{s.label}</Badge>
          </span>
          <span className="mt-0.5 block text-sm text-ink-soft">{item.summary}</span>
        </div>
        {needsMarketCheck && onRunMarketChecks && (
          <Button
            size="sm"
            variant="secondary"
            loading={busyMarketChecks}
            onClick={onRunMarketChecks}
            className="shrink-0 gap-1.5 text-xs font-semibold text-port hover:bg-port-50"
          >
            <Play className="h-3.5 w-3.5" /> Run check now
          </Button>
        )}
        {hasDetails && (
          <button
            onClick={() => setOpen((o) => !o)}
            className="p-1 text-ink-faint transition hover:text-ink"
            aria-label="Toggle details"
          >
            <ChevronDown className={cn("h-4 w-4 shrink-0 transition", open && "rotate-180")} />
          </button>
        )}
      </div>
      <AnimatePresence initial={false}>
        {open && hasDetails && (
          <motion.ul
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden pl-[76px] pr-5"
          >
            {item.details.map((d) => (
              <li key={d} className="mb-2 flex gap-2 text-sm text-ink">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-port-300" />
                {d}
              </li>
            ))}
            <li className="h-2" />
          </motion.ul>
        )}
      </AnimatePresence>
    </li>
  );
}

function InconsistencyCard({
  item,
  shipment,
  onChange,
  closed,
}: {
  item: Inconsistency;
  shipment: ShipmentDetail;
  onChange: (s: ShipmentDetail) => void;
  closed: boolean;
}) {
  const toast = useToast();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [showNoteInput, setShowNoteInput] = useState(false);
  const [brokerNote, setBrokerNote] = useState("Verified trade variation with importer");

  const isResolved = !!item.resolved;
  const isIssue = item.severity === "issue" && !isResolved;

  // Handle inline edit save
  async function handleSaveEdit(sourceKey: string) {
    if (!editValue.trim()) return;
    setSaving(true);
    try {
      if (sourceKey === "Shipment") {
        const updatePayload: Record<string, string> = {};
        if (item.field === "Container number") updatePayload.container_number = editValue.trim();
        else if (item.field === "Consignee") updatePayload.importer = editValue.trim();
        else if (item.field === "Shipper") updatePayload.exporter = editValue.trim();
        else if (item.field === "Country of origin") updatePayload.origin = editValue.trim();
        else updatePayload.product_description = editValue.trim();

        const updated = await api.updateShipment(shipment.id, updatePayload);
        onChange(updated);
        toast(`Shipment ${item.field} updated to "${editValue.trim()}". Risk recalculated.`, "success");
      } else {
        // Document field edit
        const docTypeMap: Record<string, string> = {
          "Commercial Invoice": "commercial_invoice",
          "Packing List": "packing_list",
          "Bill of Lading": "bill_of_lading",
        };
        const dt = docTypeMap[sourceKey];
        const doc = shipment.documents.find((d) => d.doc_type === dt);
        if (doc) {
          const fieldKeyMap: Record<string, string> = {
            "Container number": "container_number",
            Consignee: "consignee",
            Shipper: "shipper",
            "Gross weight": "gross_weight",
            Quantity: "quantity",
            "Total value": "total_value",
            "Country of origin": "country_of_origin",
          };
          const fKey = fieldKeyMap[item.field] || item.field.toLowerCase().replace(/\s+/g, "_");
          const updated = await api.editField(shipment.id, doc.id, fKey, editValue.trim());
          onChange(updated);
          toast(`Updated ${item.field} on ${sourceKey}.`, "success");
        } else {
          // Fallback to inconsistency resolve API
          const updated = await api.resolveInconsistency(shipment.id, {
            action: "apply",
            field: item.field,
            chosen_value: editValue.trim(),
            doc_name: sourceKey,
          });
          onChange(updated);
          toast(`Updated ${item.field} to "${editValue.trim()}".`, "success");
        }
      }
      setEditingKey(null);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to save edit.", "error");
    } finally {
      setSaving(false);
    }
  }

  // Handle one-click apply to shipment
  async function handleApplyToShipment(chosenVal: string, sourceName: string) {
    setSaving(true);
    try {
      const updated = await api.resolveInconsistency(shipment.id, {
        action: "apply",
        field: item.field,
        chosen_value: chosenVal,
        doc_name: sourceName,
      });
      onChange(updated);
      toast(`Synchronized Shipment ${item.field} to match ${sourceName}: "${chosenVal}".`, "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not apply value.", "error");
    } finally {
      setSaving(false);
    }
  }

  // Handle broker dismiss / accept
  async function handleDismiss(noteText?: string) {
    setSaving(true);
    try {
      const updated = await api.resolveInconsistency(shipment.id, {
        action: "dismiss",
        field: item.field,
        note: noteText || brokerNote,
      });
      onChange(updated);
      setShowNoteInput(false);
      toast(`Discrepancy for ${item.field} accepted by broker. Risk score reduced.`, "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not resolve discrepancy.", "error");
    } finally {
      setSaving(false);
    }
  }

  // Handle reopen
  async function handleReopen() {
    setSaving(true);
    try {
      const updated = await api.resolveInconsistency(shipment.id, {
        action: "reopen",
        field: item.field,
      });
      onChange(updated);
      toast(`Reopened discrepancy for ${item.field}.`, "info");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not reopen.", "error");
    } finally {
      setSaving(false);
    }
  }

  const shipmentVal = item.values["Shipment"];

  return (
    <div
      className={cn(
        "flex flex-col justify-between rounded-2xl border p-5 transition-all shadow-sm",
        isResolved
          ? "border-signal-green/30 bg-signal-green/[.03]"
          : isIssue
          ? "border-signal-red/25 bg-signal-red/[.04]"
          : "border-signal-amber/30 bg-signal-amber/[.05]"
      )}
    >
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-display font-bold text-ink">{item.field}</p>
          {isResolved ? (
            <Badge tone="green" dot>
              Resolved
            </Badge>
          ) : (
            <Badge tone={item.severity === "issue" ? "red" : "amber"}>
              {item.severity === "issue" ? "Mismatch" : "Minor difference"}
            </Badge>
          )}
        </div>
        <p className="mt-1 text-sm text-ink-soft">{item.message}</p>

        {/* Values list with inline editing & quick-sync chips */}
        <div className="mt-4 space-y-2.5">
          {Object.entries(item.values).map(([k, v]) => {
            const isShipment = k === "Shipment";
            const differsFromShipment = shipmentVal && v !== shipmentVal;
            const isRowEditing = editingKey === k;

            return (
              <div
                key={k}
                className={cn(
                  "rounded-xl border p-2.5 transition",
                  isShipment ? "border-port/20 bg-white" : "border-alice-200/60 bg-white/70"
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-ink-faint">{k}</span>
                  {!closed && !isRowEditing && !isResolved && (
                    <div className="flex items-center gap-1.5">
                      {!isShipment && differsFromShipment && (
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() => handleApplyToShipment(v, k)}
                          className="inline-flex items-center gap-1 rounded-md bg-port-50 px-2 py-0.5 text-xs font-semibold text-port transition hover:bg-port hover:text-white"
                          title={`Click to set Shipment ${item.field} to "${v}"`}
                        >
                          <ArrowRight className="h-3 w-3" /> Use for Shipment
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          setEditingKey(k);
                          setEditValue(v);
                        }}
                        className="rounded p-1 text-ink-faint hover:bg-alice hover:text-ink"
                        title={`Edit ${k} value`}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>

                {isRowEditing ? (
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      autoFocus
                      className="field-input !py-1 text-sm"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleSaveEdit(k);
                        if (e.key === "Escape") setEditingKey(null);
                      }}
                      placeholder={`Enter new ${item.field}`}
                    />
                    <Button
                      size="sm"
                      loading={saving}
                      onClick={() => handleSaveEdit(k)}
                      className="px-2.5 text-xs"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditingKey(null)}
                      className="px-2 text-xs"
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ) : (
                  <p
                    className={cn(
                      "mt-1 text-sm font-semibold break-words",
                      isShipment ? "text-prussian" : "text-ink"
                    )}
                  >
                    {v}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Card footer actions */}
      <div className="mt-4 pt-3 border-t border-alice-200/60">
        {isResolved ? (
          <div className="flex items-center justify-between gap-2 text-xs text-signal-green">
            <span className="flex items-center gap-1.5 font-medium">
              <CheckCircle2 className="h-4 w-4" />
              {item.resolved_note || "Approved variation by broker"}
            </span>
            {!closed && (
              <button
                type="button"
                onClick={handleReopen}
                disabled={saving}
                className="inline-flex items-center gap-1 font-semibold text-ink-soft hover:text-ink"
              >
                <RotateCcw className="h-3 w-3" /> Undo
              </button>
            )}
          </div>
        ) : showNoteInput ? (
          <div className="space-y-2">
            <input
              autoFocus
              className="field-input !py-1.5 text-xs"
              value={brokerNote}
              onChange={(e) => setBrokerNote(e.target.value)}
              placeholder="Reason for acceptance (e.g. trade name variation)"
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                loading={saving}
                onClick={() => handleDismiss()}
                className="text-xs"
              >
                Confirm Approval
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setShowNoteInput(false)}
                className="text-xs"
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs text-ink-faint">Affects risk score by +38 pts</span>
            {!closed && (
              <Button
                size="sm"
                variant="secondary"
                disabled={saving}
                onClick={() => setShowNoteInput(true)}
                className="gap-1.5 text-xs"
              >
                <ShieldCheck className="h-3.5 w-3.5 text-signal-green" /> Accept variation
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function ComplianceStep({
  shipment,
  onChange,
  closed,
}: {
  shipment: ShipmentDetail;
  onChange: (s: ShipmentDetail) => void;
  closed: boolean;
}) {
  const toast = useToast();
  const [reconciling, setReconciling] = useState(false);
  const [marketBusy, setMarketBusy] = useState(false);

  const compliance = shipment.compliance;
  if (!compliance) return <Card className="p-10 text-center text-ink-soft">Compliance checks run after you confirm the extracted data.</Card>;

  const inconsistencies = compliance.inconsistencies || [];
  const openInconsistencies = inconsistencies.filter((i) => !i.resolved);
  const resolvedCount = inconsistencies.length - openInconsistencies.length;

  const banner = {
    clear: { cls: "from-signal-green/10 ring-signal-green/25 text-[#05603A]", icon: CheckCircle2 },
    needs_review: { cls: "from-signal-amber/10 ring-signal-amber/30 text-[#93370D]", icon: AlertTriangle },
    action_required: { cls: "from-signal-red/10 ring-signal-red/25 text-[#912018]", icon: AlertOctagon },
  }[compliance.overall];

  // Reconcile all inconsistencies from documents in 1 click
  async function handleReconcileAll() {
    setReconciling(true);
    try {
      const updated = await api.reconcileAll(shipment.id);
      onChange(updated);
      toast("✨ All inconsistencies reconciled with official shipping documents! Risk score reduced.", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to auto-reconcile.", "error");
    } finally {
      setReconciling(false);
    }
  }

  // Quick run counterparty / market checks to drop risk
  async function handleRunMarketChecks() {
    setMarketBusy(true);
    try {
      const updated = await api.verify(shipment.id, undefined, false);
      onChange(updated);
      toast("Market & counterparty checks complete. Compliance updated.", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not run market checks.", "error");
    } finally {
      setMarketBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-2xl font-bold text-ink">Compliance checks</h2>
        <p className="mt-1 text-ink-soft">What the copilot checked, what it found, and what still needs a person.</p>
      </div>

      <div className={cn("flex items-center gap-3 rounded-2xl bg-gradient-to-r to-white p-4 ring-1", banner.cls)}>
        <banner.icon className="h-5 w-5 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold">Review status: {compliance.review_status}</p>
          <p className="text-[13px] opacity-80">
            {compliance.alert_count} item{compliance.alert_count === 1 ? "" : "s"} need{compliance.alert_count === 1 ? "s" : ""} attention
          </p>
        </div>
        {openInconsistencies.length > 0 && !closed && (
          <Button
            size="sm"
            onClick={handleReconcileAll}
            loading={reconciling}
            className="gap-1.5 shadow-sm bg-gradient-to-r from-port to-port-600 text-white"
          >
            <Sparkles className="h-3.5 w-3.5 text-amber-300" />
            Quick Reconcile All
          </Button>
        )}
      </div>

      {/* Risk Reduction Quick-Action Banner */}
      {(openInconsistencies.length > 0 || shipment.risk_level === "high") && !closed && (
        <div className="relative overflow-hidden rounded-2xl border border-port/25 bg-gradient-to-r from-port-50/80 via-white to-alice/60 p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-port text-white">
                <ShieldAlert className="h-5 w-5" />
              </span>
              <div>
                <p className="text-sm font-bold text-prussian">
                  Reduce Risk Score ({shipment.risk_score}/100 → Low Risk)
                </p>
                <p className="text-xs text-ink-soft">
                  Resolving {openInconsistencies.length} open document discrepancies cuts up to 30 risk points.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={handleRunMarketChecks}
                loading={marketBusy}
                className="gap-1.5 text-xs font-semibold"
              >
                <Play className="h-3.5 w-3.5 text-port" /> Counterparty check
              </Button>
              <Button
                size="sm"
                onClick={handleReconcileAll}
                loading={reconciling}
                className="gap-1.5 text-xs font-semibold"
              >
                <Sparkles className="h-3.5 w-3.5 text-amber-300" /> Resolve all ({openInconsistencies.length})
              </Button>
            </div>
          </div>
        </div>
      )}

      <MarketChecksPanel shipment={shipment} onChange={onChange} closed={closed} />

      <Card className="overflow-hidden">
        <ul className="divide-y divide-alice-200/70">
          {compliance.items.map((i) => (
            <Row
              key={i.id}
              item={i}
              onRunMarketChecks={handleRunMarketChecks}
              busyMarketChecks={marketBusy}
            />
          ))}
        </ul>
      </Card>

      {/* Data Inconsistencies Section with in-place editing */}
      {inconsistencies.length > 0 && (
        <Card className="p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-display text-base font-bold text-ink">Data inconsistencies</h3>
                {openInconsistencies.length > 0 ? (
                  <Badge tone="red">{openInconsistencies.length} open</Badge>
                ) : (
                  <Badge tone="green" dot>
                    All {inconsistencies.length} resolved
                  </Badge>
                )}
                {resolvedCount > 0 && openInconsistencies.length > 0 && (
                  <span className="text-xs text-signal-green">({resolvedCount} resolved)</span>
                )}
              </div>
              <p className="mt-1 text-sm text-ink-soft">
                Edit values directly below, click "Use for Shipment" to sync, or accept minor variations.
              </p>
            </div>
            {!closed && openInconsistencies.length > 0 && (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleReconcileAll}
                loading={reconciling}
                className="gap-1.5 border-port/30 text-port hover:bg-port-50"
              >
                <Sparkles className="h-4 w-4" /> Reconcile all from documents
              </Button>
            )}
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {inconsistencies.map((i, idx) => (
              <InconsistencyCard
                key={idx}
                item={i}
                shipment={shipment}
                onChange={onChange}
                closed={closed}
              />
            ))}
          </div>
        </Card>
      )}

      <Card className="p-6">
        <div className="flex items-center gap-2.5">
          <ScrollText className="h-5 w-5 text-port" />
          <h3 className="font-display text-base font-bold text-ink">Certificates usually required</h3>
        </div>
        <ul className="mt-4 grid gap-2.5 sm:grid-cols-2">
          {compliance.certificates.map((c) => (
            <li
              key={c.name}
              className="flex items-center justify-between gap-3 rounded-xl bg-alice/70 px-4 py-3"
            >
              <span className="text-sm font-medium text-ink">
                {c.name}
                {c.source ? ` [${c.source}]` : ""}
              </span>
              <Badge tone="amber">{c.status}</Badge>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-ink-faint">Basis: {compliance.rules_basis ?? compliance.rules}</p>
      </Card>
    </div>
  );
}
