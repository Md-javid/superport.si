"use client";
import { Database, FileText, RefreshCw, Search, Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, SectionTitle, Skeleton } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { LibraryDoc, LibraryHit, RagStatus } from "@/lib/types";
import { cn, formatBytes, timeAgo } from "@/lib/utils";

export default function LibraryPage() {
  const toast = useToast();
  const [data, setData] = useState<{ status: RagStatus; documents: LibraryDoc[] } | null>(null);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<"library" | "org">("library");
  const [hits, setHits] = useState<LibraryHit[] | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const load = useCallback(() => api.library().then(setData).catch((e) => toast(e.message, "error")), [toast]);
  useEffect(() => { load(); }, [load]);

  async function upload(f: File) {
    setBusy("upload");
    try { await api.uploadLibrary(f, title, tags); toast("Document added and indexed.", "success"); setTitle(""); setTags(""); await load(); }
    catch (e) { toast(e instanceof Error ? e.message : "Could not add the document.", "error"); } finally { setBusy(null); }
  }
  async function act(name: string, fn: () => Promise<unknown>, ok: string) {
    setBusy(name);
    try { await fn(); toast(ok, "success"); await load(); } catch (e) { toast(e instanceof Error ? e.message : "Something went wrong.", "error"); } finally { setBusy(null); }
  }
  async function find(e: FormEvent) {
    e.preventDefault();
    setBusy("search");
    try { setHits(await api.searchLibrary(q, scope)); } catch (err) { toast(err instanceof Error ? err.message : "Search failed.", "error"); } finally { setBusy(null); }
  }

  if (!data) return <Skeleton className="h-64" />;
  const st = data.status;
  return (
    <div className="space-y-6">
      <div><h1 className="font-display text-3xl font-extrabold text-prussian">Library</h1><p className="mt-1 max-w-2xl text-ink-soft">Your own SOPs, regulations and rate sheets. The Copilot searches them with every answer and cites the page. Only your organisation can see them.</p></div>

      <Card className="p-6">
        <div className="flex flex-wrap items-center gap-3"><Database className="h-5 w-5 text-port" /><h2 className="font-display text-base font-bold text-ink">Search index</h2>
          <Badge tone={st.vector_store === "pgvector" ? "green" : "amber"} dot>{st.vector_store === "pgvector" ? "PostgreSQL + pgvector" : "Local store (development)"}</Badge>
          <Badge tone={st.semantic ? "green" : "amber"}>{st.semantic ? "Semantic search (Gemini)" : "Keyword matching"}</Badge></div>
        <p className="mt-2 text-sm text-ink-soft">{st.chunks.toLocaleString()} passages from {st.library_docs} library document{st.library_docs === 1 ? "" : "s"} and your shipments. Embedder: <span className="font-mono text-xs">{st.embedder}</span>.</p>
        {!st.semantic && <p className="mt-2 rounded-xl bg-signal-amber/10 px-3.5 py-2.5 text-sm text-[#7A2E0E]">Without a Gemini key this matches words, not meaning. Add one for semantic search.</p>}
        {st.pgvector_error && st.vector_store === "local" && <p className="mt-2 text-xs text-ink-faint">pgvector is not active: {st.pgvector_error}</p>}
        <div className="mt-4 flex flex-wrap gap-2">
          {st.library_stale > 0 && <Button size="sm" onClick={() => act("reindex", api.reindexLibrary, "Library re-indexed.")} loading={busy === "reindex"}><RefreshCw className="h-4 w-4" /> Re-index {st.library_stale} document{st.library_stale > 1 ? "s" : ""}</Button>}
          <Button size="sm" variant="secondary" onClick={() => act("ship", api.indexShipments, "Shipments indexed.")} loading={busy === "ship"}>Index all my shipments</Button>
        </div>
      </Card>

      <div className="grid items-start gap-6 xl:grid-cols-[1.3fr_1fr]">
        <Card className="p-6">
          <SectionTitle title="Search" hint="Find a procedure, a rule or a past shipment document." />
          <form onSubmit={find} className="mt-4 flex flex-wrap gap-2.5">
            <input className="field-input min-w-[220px] flex-1" placeholder="For example: what do we need for lithium batteries" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
            <select className="field-input !w-auto" value={scope} onChange={(e) => setScope(e.target.value as "library" | "org")} aria-label="Scope"><option value="library">Library only</option><option value="org">Library and shipments</option></select>
            <Button type="submit" loading={busy === "search"} disabled={q.trim().length < 2}><Search className="h-4 w-4" /> Search</Button>
          </form>
          {hits && hits.length === 0 && <p className="mt-4 text-sm text-ink-soft">Nothing relevant found.</p>}
          <ul className="mt-4 space-y-3">{hits?.map((h, i) => (
            <li key={i} className="rounded-xl border border-alice-200 p-3.5">
              <div className="flex flex-wrap items-center gap-2"><span className="font-semibold text-ink">{h.title}{h.page ? `, page ${h.page}` : ""}</span><Badge tone="gray">{Math.round(h.score * 100)}% match</Badge>{h.shipment_reference && <Badge tone="blue">{h.shipment_reference}</Badge>}</div>
              <p className="mt-1.5 whitespace-pre-wrap text-[13px] leading-snug text-ink-soft">{h.text}</p>
            </li>))}</ul>
        </Card>

        <Card className="p-6">
          <SectionTitle title="Add a document" hint="PDF with text, TXT, MD or CSV, up to 10 MB." />
          <div className="mt-4 space-y-2.5">
            <input className="field-input" placeholder="Title (optional)" value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Title" />
            <input className="field-input" placeholder="Tags, for example sop, battery" value={tags} onChange={(e) => setTags(e.target.value)} aria-label="Tags" />
            <Button className="w-full" onClick={() => file.current?.click()} loading={busy === "upload"}><Upload className="h-4 w-4" /> Choose a file</Button>
            <input ref={file} type="file" accept=".pdf,.txt,.md,.csv" className="sr-only" aria-label="Library file" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
          </div>
          <ul className="mt-5 divide-y divide-alice-200/70">
            {data.documents.map((d) => (
              <li key={d.id} className="flex items-start justify-between gap-3 py-3">
                <div className="min-w-0"><p className="flex items-center gap-2 font-semibold text-ink"><FileText className="h-4 w-4 shrink-0 text-port" /><span className="truncate">{d.title}</span></p>
                  <p className="text-xs text-ink-faint">{d.chunk_count} passages, {formatBytes(d.size_bytes)}, {d.created_by}, {timeAgo(d.created_at)}</p>{d.stale && <Badge tone="amber">Needs re-index</Badge>}</div>
                <button onClick={() => act(`del${d.id}`, () => api.deleteLibrary(d.id), "Document removed.")} aria-label={`Delete ${d.title}`} className={cn("rounded-md p-1.5 text-ink-faint hover:bg-signal-red/10 hover:text-signal-red", busy === `del${d.id}` && "opacity-50")}><Trash2 className="h-4 w-4" /></button>
              </li>))}
            {data.documents.length === 0 && <li className="py-4 text-sm text-ink-soft">No documents yet.</li>}
          </ul>
        </Card>
      </div>
    </div>
  );
}
