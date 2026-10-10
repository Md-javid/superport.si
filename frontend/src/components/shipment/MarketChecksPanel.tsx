"use client";
import { Building2, ExternalLink, FlaskConical, Play, RefreshCw, Scale, Tags } from "lucide-react";
import { useState } from "react";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { ShipmentDetail } from "@/lib/types";
import { EvidenceList } from "./EvidenceList";

const LEVEL: Record<string, { tone: Tone; label: string }> = {
  low: { tone: "green", label: "Low" }, medium: { tone: "amber", label: "Medium" }, high: { tone: "red", label: "High" }, unknown: { tone: "gray", label: "Unknown" },
};
const VERDICT: Record<string, { tone: Tone; label: string }> = { adverse: { tone: "red", label: "Adverse" }, possible: { tone: "amber", label: "Possible match" } };
const host = (u: string) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; } };

function Sample({ mode }: { mode?: string }) {
  return mode === "fixture" ? <Badge tone="amber"><FlaskConical className="h-3 w-3" /> Sample data</Badge> : <Badge tone="blue">Live</Badge>;
}

export function MarketChecksPanel({ shipment, onChange, closed }: { shipment: ShipmentDetail; onChange: (s: ShipmentDetail) => void; closed: boolean }) {
  const toast = useToast();
  const [busy, setBusy] = useState<"run" | "refresh" | null>(null);
  const { intel, verification } = shipment;

  async function run(force: boolean) {
    setBusy(force ? "refresh" : "run");
    try {
      onChange(await api.verify(shipment.id, undefined, force));
      toast("Market checks complete. Compliance and risk were updated.", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not run the checks.", "error");
    } finally {
      setBusy(null);
    }
  }

  const price = intel?.price, company = intel?.company, rules = intel?.rules;
  return (
    <Card className="space-y-5 p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="font-display text-lg font-bold text-ink">Live market checks</h3>
          <p className="mt-1 max-w-xl text-sm text-ink-soft">Price against live listings, a look at the importer and exporter, and a cited list of import rules. Web results are signals to check, not final authority.</p>
        </div>
        {!closed && (
          <div className="flex gap-2">
            <Button onClick={() => run(false)} loading={busy === "run"} disabled={!verification.available}><Play className="h-4 w-4" /> {intel ? "Update checks" : "Run checks"}</Button>
            {intel && <Button variant="secondary" onClick={() => run(true)} loading={busy === "refresh"} disabled={!verification.available}><RefreshCw className="h-4 w-4" /> Fresh data</Button>}
          </div>
        )}
      </div>
      {!verification.available && <p className="rounded-xl bg-alice px-3.5 py-2.5 text-sm text-ink-soft">{verification.reason}</p>}
      {verification.available && !intel && <p className="rounded-xl bg-port-50/70 px-3.5 py-2.5 text-sm text-prussian-700">{verification.sample ? "Sample data will be shown (this is a demo shipment or fixtures mode). No credits are used." : "Uses about 7 SerpApi searches and 2 to 3 Gemini calls. Results are cached."}</p>}

      {price && (
        <section className="rounded-xl border border-alice-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="flex items-center gap-2 font-display font-bold text-ink"><Tags className="h-4 w-4 text-port" /> Price check</h4><div className="flex gap-2"><Sample mode={price.source_mode} />{price.level && <Badge tone={LEVEL[price.level].tone} dot>{LEVEL[price.level].label}</Badge>}</div></div>
          <p className="mt-2 text-sm text-ink-soft">{price.summary}</p>
          {price.market && <p className="mt-2 text-[13px] text-ink-faint">Market range {price.market.p25.toLocaleString()} to {price.market.p75.toLocaleString()} USD (min {price.market.min.toLocaleString()}, max {price.market.max.toLocaleString()}){price.filtered_by_ai ? ", filtered by AI for comparable listings" : ""}.</p>}
          {price.listings && price.listings.length > 0 && (
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">{price.listings.map((l) => (
              <li key={l.url || l.title} className="rounded-lg bg-alice/70 px-3 py-2 text-[13px]">
                <p className="truncate font-medium text-ink">{l.title}</p>
                <p className="flex items-center justify-between text-ink-soft"><span>{l.price.toLocaleString()} USD, {l.source}</span>{l.url && <a href={l.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-semibold text-port"><ExternalLink className="h-3 w-3" /></a>}</p>
              </li>))}</ul>
          )}
        </section>
      )}

      {company && (
        <section className="rounded-xl border border-alice-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="flex items-center gap-2 font-display font-bold text-ink"><Building2 className="h-4 w-4 text-port" /> Counterparties</h4><Sample mode={company.source_mode} /></div>
          {company.status !== "ok" && <p className="mt-2 text-sm text-ink-soft">{company.summary}</p>}
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {company.parties?.map((p) => (
              <div key={p.role} className="rounded-lg bg-alice/60 p-3.5">
                <div className="flex items-start justify-between gap-2"><div className="min-w-0"><p className="text-xs font-semibold text-ink-faint">{p.role}</p><p className="truncate font-semibold text-ink">{p.name}</p></div><Badge tone={LEVEL[p.level].tone} dot>{LEVEL[p.level].label}</Badge></div>
                <p className="mt-1.5 text-[13px] text-ink-soft">{p.summary}</p>
                {p.place && <p className="mt-1.5 text-xs text-ink-faint">{p.place.address}{p.place.rating ? `, rating ${p.place.rating} (${p.place.reviews ?? 0} reviews)` : ""}</p>}
                {p.articles.map((a) => (
                  <div key={a.url} className="mt-2 rounded-lg border border-alice-200 bg-white p-2.5">
                    <div className="flex items-start justify-between gap-2"><a href={a.url} target="_blank" rel="noopener noreferrer" className="text-[13px] font-semibold text-ink hover:text-port">{a.title}</a><Badge tone={VERDICT[a.verdict].tone}>{VERDICT[a.verdict].label}</Badge></div>
                    <p className="mt-1 text-xs text-ink-faint">{a.source || host(a.url)}{a.date ? `, ${a.date}` : ""}. {a.reason}</p>
                  </div>
                ))}
              </div>
            ))}
          </div>
          {company.disclaimer && <p className="mt-3 text-xs text-ink-faint">{company.disclaimer} Similar names are common; a person must confirm any match.</p>}
        </section>
      )}

      {rules && (
        <section className="rounded-xl border border-alice-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="flex items-center gap-2 font-display font-bold text-ink"><Scale className="h-4 w-4 text-port" /> Import rules for {shipment.destination}</h4><Sample mode={rules.source_mode} /></div>
          <p className="mt-2 text-sm text-ink-soft">{rules.summary}</p>
          {(rules.restrictions?.length || rules.certificates?.length || rules.duty_notes?.length) ? (
            <ul className="mt-3 space-y-1.5 text-sm text-ink">
              {rules.restrictions?.map((r) => <li key={r.text}>{r.text} <span className="text-ink-faint">[{r.source}]</span></li>)}
              {rules.certificates?.map((c) => <li key={c.name}>Certificate: {c.name} <Badge tone={c.level === "required" ? "amber" : "gray"}>{c.level}</Badge> <span className="text-ink-faint">[{c.source}]</span></li>)}
              {rules.duty_notes?.map((d) => <li key={d.text}>Duty: {d.text} <span className="text-ink-faint">[{d.source}]</span></li>)}
            </ul>
          ) : null}
          {rules.sources && rules.sources.length > 0 && <details className="mt-3"><summary className="cursor-pointer text-sm font-semibold text-port">Sources ({rules.sources.length})</summary><div className="mt-3"><EvidenceList sources={rules.sources} mode={rules.source_mode} /></div></details>}
        </section>
      )}
    </Card>
  );
}
