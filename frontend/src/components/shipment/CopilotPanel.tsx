"use client";
import { motion } from "framer-motion";
import { AlertTriangle, BookOpen, ExternalLink, Lock, Mail, Send, ShieldCheck, Sparkles } from "lucide-react";
import { Fragment, useEffect, useRef, useState, type FormEvent } from "react";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { PARTY_LABEL, type CopilotAnswer, type Draft, type EvidenceFact, type PartyRole } from "@/lib/types";
import { cn } from "@/lib/utils";

const SUGGESTIONS = ["Why is this shipment delayed?", "What documents are missing and who owes them?", "What does the invoice say about quantity and value?", "What was said in the discussion?"];
const OWNER_EXTRA = ["What is the risk and which HS code applies?", "What certificates do we need for lithium batteries?"];
const TYPE_TONE: Record<string, Tone> = { document: "blue", library: "navy", comment: "gray", timeline: "green", eta: "amber", tracking: "amber", checklist: "amber", signal: "red", hs: "blue", compliance: "amber", risk: "red" };

function Answer({ a }: { a: CopilotAnswer }) {
  const [open, setOpen] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const byId = Object.fromEntries(a.evidence.map((e) => [e.id, e])) as Record<string, EvidenceFact>;
  const parts = a.answer.split(/(\[E\d+\])/g);
  const used = new Set(a.answer.match(/\[E\d+\]/g)?.map((m) => m.slice(1, -1)) ?? []);
  return (
    <div className="rounded-2xl border border-alice-200 bg-white p-4">
      <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-ink">
        {parts.map((p, i) => /^\[E\d+\]$/.test(p) ? (
          <button key={i} onClick={() => { setOpen(open === p.slice(1, -1) ? null : p.slice(1, -1)); setAll(true); }} className="mx-0.5 rounded-md bg-port-50 px-1.5 py-0.5 align-baseline text-xs font-bold text-port-600 hover:bg-port hover:text-white" aria-label={`Show evidence ${p}`}>{p.slice(1, -1)}</button>
        ) : <Fragment key={i}>{p}</Fragment>)}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {a.grounded ? <Badge tone="green"><ShieldCheck className="h-3 w-3" /> Grounded in {used.size || a.evidence.length} source{(used.size || a.evidence.length) === 1 ? "" : "s"}</Badge> : <Badge tone="amber"><AlertTriangle className="h-3 w-3" /> Not grounded: check before relying on it</Badge>}
        {a.agents.map((g) => <Badge key={g.agent} tone={g.restricted ? "amber" : g.facts ? "blue" : "gray"}>{g.restricted && <Lock className="h-3 w-3" />}{g.title}{g.facts ? ` (${g.facts})` : ""}</Badge>)}
        <span className="text-xs text-ink-faint">Engine: {a.engine === "rules" ? "rules, no AI summariser" : a.engine}</span>
      </div>
      {a.warning && <p className="mt-2 rounded-lg bg-signal-amber/10 px-3 py-2 text-xs text-[#93370D]">{a.warning}</p>}
      {a.missing && a.missing.length > 0 && <p className="mt-2 text-sm text-ink-soft"><span className="font-semibold">Not found:</span> {a.missing.join("; ")}</p>}
      <button onClick={() => setAll(!all)} className="mt-3 text-sm font-semibold text-port">{all ? "Hide evidence" : `Show evidence (${a.evidence.length})`}</button>
      {all && (
        <ul className="mt-2 space-y-2">
          {a.evidence.map((e) => (
            <li key={e.id} className={cn("rounded-xl border p-3 text-[13px]", open === e.id ? "border-port bg-port-50/50" : "border-alice-200")}>
              <div className="flex flex-wrap items-center gap-2"><span className="font-bold text-port-600">{e.id}</span><Badge tone={TYPE_TONE[e.source.type] ?? "gray"}>{e.source.label}</Badge>{e.source.url && <a href={e.source.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-port">Source <ExternalLink className="h-3 w-3" /></a>}{typeof e.source.score === "number" && <span className="text-xs text-ink-faint">match {Math.round(e.source.score * 100)}%</span>}</div>
              <p className="mt-1 whitespace-pre-wrap text-ink-soft">{e.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function CopilotPanel({ shipmentId, owner, partnerRoles }: { shipmentId: number; owner: boolean; partnerRoles: PartyRole[] }) {
  const toast = useToast();
  const [items, setItems] = useState<(CopilotAnswer & { question: string })[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [aud, setAud] = useState<PartyRole>(partnerRoles[0] ?? "forwarder");
  const [drafting, setDrafting] = useState(false);
  const [sending, setSending] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => { api.copilotHistory(shipmentId).then((h) => setItems(h as (CopilotAnswer & { question: string })[])).catch(() => {}); }, [shipmentId]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [items.length, busy]);

  async function ask(text: string) {
    if (text.trim().length < 3) return;
    setBusy(true);
    setQ("");
    try { const a = await api.ask(shipmentId, text.trim()); setItems((s) => [...s, { ...a, question: text.trim() }]); }
    catch (e) { toast(e instanceof Error ? e.message : "The copilot could not answer.", "error"); setQ(text); }
    finally { setBusy(false); }
  }
  async function makeDraft() {
    setDrafting(true);
    try { setDraft(await api.draftUpdate(shipmentId, aud)); } catch (e) { toast(e instanceof Error ? e.message : "Could not draft.", "error"); } finally { setDrafting(false); }
  }
  async function send() {
    if (!draft) return;
    setSending(true);
    try { const r = await api.sendUpdate(shipmentId, [draft.audience], draft.subject, draft.body); toast(`Update sent to ${r.sent_to} ${r.sent_to === 1 ? "person" : "people"}.`, "success"); setDraft(null); }
    catch (e) { toast(e instanceof Error ? e.message : "Could not send.", "error"); } finally { setSending(false); }
  }

  const suggestions = owner ? [...SUGGESTIONS, ...OWNER_EXTRA] : SUGGESTIONS;
  return (
    <Card className="overflow-hidden">
      <div className="relative overflow-hidden bg-gradient-to-br from-prussian via-prussian-700 to-port px-6 py-5 text-white">
        <div className="absolute -right-10 -top-12 h-40 w-40 rounded-full bg-port-300/40 blur-3xl animate-aurora" />
        <div className="relative flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-white/15"><Sparkles className="h-5 w-5" /></span>
          <div><h2 className="font-display text-lg font-bold">Shipment Copilot</h2><p className="text-sm text-white/70">Ask in plain words. Every answer shows its sources, and says so when it cannot find something.</p></div></div>
      </div>
      <div className="space-y-4 p-6">
        <div className="flex flex-wrap gap-2">{suggestions.map((s) => <button key={s} onClick={() => ask(s)} disabled={busy} className="rounded-full border border-alice-200 bg-alice/60 px-3 py-1.5 text-[13px] font-medium text-ink-soft transition hover:border-port-300 hover:bg-port-50 disabled:opacity-50">{s}</button>)}</div>
        <div className="max-h-[560px] space-y-5 overflow-y-auto pr-1">
          {items.map((it) => (
            <motion.div key={it.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-2.5">
              <div className="ml-auto w-fit max-w-[85%] rounded-2xl bg-port px-4 py-2.5 text-[15px] text-white">{it.question}</div>
              <Answer a={it} />
              {it.follow_ups && it.follow_ups.length > 0 && <div className="flex flex-wrap gap-2">{it.follow_ups.map((f) => <button key={f} onClick={() => ask(f)} className="text-[13px] font-semibold text-port hover:text-port-600">{f}</button>)}</div>}
            </motion.div>
          ))}
          {busy && <p className="flex items-center gap-2 text-sm text-ink-soft"><Sparkles className="h-4 w-4 animate-pulse text-port" /> Consulting the specialists...</p>}
          <div ref={end} />
        </div>
        <form onSubmit={(e: FormEvent) => { e.preventDefault(); ask(q); }} className="flex gap-2.5">
          <input className="field-input" placeholder="Ask about this shipment" value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} aria-label="Question" />
          <Button type="submit" loading={busy} disabled={q.trim().length < 3} aria-label="Ask"><Send className="h-4 w-4" /></Button>
        </form>

        {owner && (
          <div className="border-t border-alice-200 pt-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-ink"><Mail className="h-4 w-4 text-port" /> Customer update</p>
            <p className="mt-0.5 text-[13px] text-ink-soft">The copilot drafts it from the shipment facts. You edit and send. Nothing goes out on its own.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <select className="field-input !w-auto !py-2" value={aud} onChange={(e) => setAud(e.target.value as PartyRole)} aria-label="Audience">{(Object.keys(PARTY_LABEL) as PartyRole[]).map((r) => <option key={r} value={r}>{PARTY_LABEL[r]}</option>)}</select>
              <Button size="sm" variant="secondary" onClick={makeDraft} loading={drafting}><BookOpen className="h-4 w-4" /> Draft update</Button>
            </div>
            {draft && (
              <div className="mt-3 space-y-2.5 rounded-xl bg-alice/70 p-4">
                {draft.warning && <p className="text-xs text-[#93370D]">{draft.warning}</p>}
                <input className="field-input !py-2" value={draft.subject} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} aria-label="Subject" />
                <textarea rows={9} className="field-input resize-y" value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} aria-label="Message" />
                <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs text-ink-faint">Drafted by {draft.engine === "template" ? "a standard template" : draft.engine}</span>
                  <div className="flex gap-2"><Button size="sm" variant="ghost" onClick={() => setDraft(null)}>Discard</Button><Button size="sm" onClick={send} loading={sending}><Send className="h-4 w-4" /> Send to {PARTY_LABEL[draft.audience].toLowerCase()}</Button></div></div>
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
