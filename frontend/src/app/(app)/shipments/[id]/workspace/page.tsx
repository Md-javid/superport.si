"use client";
import { motion } from "framer-motion";
import { ArrowLeft, BellRing, CheckCircle2, Download, FileUp, MapPin, MessageSquare, Send, Trash2, UserPlus, Workflow } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { StageBadge } from "@/components/shipment/StageBadge";
import { TimelinePanel } from "@/components/shipment/TimelinePanel";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, ProgressBar, SectionTitle, Skeleton } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { PARTY_LABEL, type ChecklistItem, type PartyRole, type Workspace } from "@/lib/types";
import { cn, formatBytes, timeAgo } from "@/lib/utils";

const ROLE_TONE: Record<PartyRole, Tone> = { broker: "navy", forwarder: "blue", importer: "green", exporter: "amber" };
const ROLES = Object.keys(PARTY_LABEL) as PartyRole[];

export default function WorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  const [ws, setWs] = useState<Workspace | null>(null);
  const [error, setError] = useState("");
  const [comment, setComment] = useState("");
  const [sending, setSending] = useState(false);
  const [busyItem, setBusyItem] = useState<number | null>(null);
  const [inv, setInv] = useState({ email: "", role: "forwarder" as PartyRole });
  const [inviting, setInviting] = useState(false);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [req, setReq] = useState({ label: "", role: "exporter" as PartyRole });
  const fileRefs = useRef<Record<number, HTMLInputElement | null>>({});

  const load = useCallback(() => api.workspace(id).then(setWs).catch((e) => setError(e.message)), [id]);
  useEffect(() => { load(); const t = setInterval(load, 20000); return () => clearInterval(t); }, [load]);

  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    try { await fn(); if (ok) toast(ok, "success"); await load(); } catch (e) { toast(e instanceof Error ? e.message : "Something went wrong.", "error"); }
  };

  async function send(e: FormEvent) {
    e.preventDefault();
    if (!comment.trim()) return;
    setSending(true);
    await run(() => api.addComment(Number(id), comment.trim()));
    setComment("");
    setSending(false);
  }
  async function invite(e: FormEvent) {
    e.preventDefault();
    setInviting(true);
    try { const r = await api.inviteToShipment(Number(id), inv.email, inv.role); setInviteLink(r.dev_link); setInv({ ...inv, email: "" }); toast(`Invitation sent to ${r.email}.`, "success"); await load(); }
    catch (err) { toast(err instanceof Error ? err.message : "Could not send the invitation.", "error"); }
    finally { setInviting(false); }
  }
  async function upload(item: ChecklistItem, file: File) {
    setBusyItem(item.id);
    await run(() => api.uploadChecklist(Number(id), item.id, file), `${item.label} uploaded.`);
    setBusyItem(null);
  }

  if (error) return <Card className="p-12 text-center"><p className="font-display text-lg font-bold">Workspace not available</p><p className="mt-1 text-sm text-ink-soft">{error}</p><Link href="/shipments" className="mt-4 inline-block font-semibold text-port">Back to shipments</Link></Card>;
  if (!ws) return <div className="space-y-4"><Skeleton className="h-28" /><Skeleton className="h-96" /></div>;

  const s = ws.shipment;
  const owner = ws.access === "owner";
  const missing = ws.checklist.filter((i) => i.status === "missing" && i.required).length;
  const canUpload = (i: ChecklistItem) => owner || i.party_role === ws.party_role;

  return (
    <div className="space-y-6">
      <Link href={owner ? `/shipments/${s.id}` : "/shipments"} className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-soft hover:text-port"><ArrowLeft className="h-4 w-4" /> {owner ? "AI workflow" : "Shipments"}</Link>

      <motion.header initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="surface relative overflow-hidden p-6">
        <div className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-port/10 blur-3xl" />
        <div className="relative flex flex-wrap items-start justify-between gap-5">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3"><h1 className="font-display text-3xl font-extrabold text-prussian">{s.reference}</h1><StageBadge stage={s.stage} label={s.stage_label} />{!owner && <Badge tone={ROLE_TONE[ws.party_role as PartyRole]}>You are the {ws.party_role}</Badge>}</div>
            <p className="mt-1.5 max-w-2xl text-ink-soft">{s.product_description}</p>
            <p className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-ink-soft"><span className="inline-flex items-center gap-1.5"><MapPin className="h-4 w-4 text-port" />{s.origin} to {s.destination}, {s.port}</span><span>{s.carrier}</span><span>{s.container_number}</span></p>
            {!owner && <p className="mt-1 text-sm text-ink-faint">Shared by {ws.owner_org}</p>}
          </div>
          <div className="w-full max-w-[230px]">
            <div className="flex justify-between text-xs font-semibold text-ink-soft"><span>Clearance progress</span><span>{s.progress}%</span></div>
            <ProgressBar value={s.progress} className="mt-2" height={8} />
            <p className={cn("mt-3 text-sm font-semibold", missing ? "text-[#B54708]" : "text-[#067647]")}>{missing ? `${missing} required document${missing > 1 ? "s" : ""} still missing` : "All required documents received"}</p>
            {owner && <Link href={`/shipments/${s.id}`} className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-port"><Workflow className="h-4 w-4" /> Open AI workflow</Link>}
          </div>
        </div>
      </motion.header>

      <div className="grid items-start gap-6 xl:grid-cols-[1.6fr_1fr]">
        <div className="space-y-6">
          <TimelinePanel shipmentId={Number(id)} ws={ws} onChanged={load} />
          <Card className="p-6">
            <SectionTitle title="Document checklist" hint="Everyone sees who must provide what." />
            <ul className="mt-4 divide-y divide-alice-200/70">
              {ws.checklist.map((i) => (
                <li key={i.id} className="flex flex-wrap items-center justify-between gap-3 py-3.5">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2"><span className="font-semibold text-ink">{i.label}</span>{!i.required && <span className="text-xs text-ink-faint">optional</span>}<Badge tone={ROLE_TONE[i.party_role]}>{PARTY_LABEL[i.party_role]}</Badge></div>
                    {i.status === "uploaded" ? <p className="mt-0.5 flex items-center gap-1.5 text-sm text-[#067647]"><CheckCircle2 className="h-4 w-4" />{i.filename} <span className="text-ink-faint">({formatBytes(i.size_bytes)}) by {i.uploaded_by}{i.uploaded_at ? `, ${timeAgo(i.uploaded_at)}` : ""}</span></p>
                      : <p className="mt-0.5 text-sm text-[#B54708]">Missing{i.last_reminder_at ? `. Reminder sent ${timeAgo(i.last_reminder_at)}` : ""}</p>}
                  </div>
                  <div className="flex items-center gap-2">
                    {i.can_download && <Button size="sm" variant="ghost" onClick={() => run(() => api.downloadChecklist(Number(id), i.id, i.filename))} aria-label={`Download ${i.label}`}><Download className="h-4 w-4" /></Button>}
                    {canUpload(i) && (<>
                      <Button size="sm" variant={i.status === "uploaded" ? "secondary" : "primary"} loading={busyItem === i.id} onClick={() => fileRefs.current[i.id]?.click()}><FileUp className="h-4 w-4" />{i.status === "uploaded" ? "Replace" : "Upload"}</Button>
                      <input ref={(el) => { fileRefs.current[i.id] = el; }} type="file" className="sr-only" aria-label={`Upload ${i.label}`} onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(i, f); e.target.value = ""; }} />
                    </>)}
                    {owner && i.status === "missing" && <Button size="sm" variant="secondary" onClick={() => run(async () => { const r = await api.remind(Number(id), i.id); toast(`Reminder sent to ${r.notified} ${r.notified === 1 ? "person" : "people"}.`, "success"); })}><BellRing className="h-4 w-4" /> Remind</Button>}
                  </div>
                </li>
              ))}
            </ul>
            {owner && (
              <form onSubmit={(e) => { e.preventDefault(); run(() => api.addChecklistItem(Number(id), req.label, req.role), "Request added.").then(() => setReq({ ...req, label: "" })); }} className="mt-4 flex flex-wrap gap-2.5 border-t border-alice-200 pt-4">
                <input className="field-input !py-2 min-w-[180px] flex-1" placeholder="Request another document, for example Delivery order" value={req.label} onChange={(e) => setReq({ ...req, label: e.target.value })} aria-label="New request" />
                <select className="field-input !w-auto !py-2" value={req.role} onChange={(e) => setReq({ ...req, role: e.target.value as PartyRole })} aria-label="Responsible party">{ROLES.map((r) => <option key={r} value={r}>{PARTY_LABEL[r]}</option>)}</select>
                <Button size="sm" type="submit" disabled={req.label.trim().length < 2}>Add request</Button>
              </form>
            )}
          </Card>

          <Card className="p-6">
            <SectionTitle title="Discussion" hint="Keep shipment talk in one place. Type @name to mention someone." />
            <ul className="mt-5 space-y-4">
              {ws.comments.length === 0 && <li className="text-sm text-ink-soft">No messages yet. Say hello to your partners.</li>}
              {ws.comments.map((c) => (
                <li key={c.id} className={cn("flex gap-3", c.mine && "flex-row-reverse")}>
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-port to-port-300 text-xs font-bold text-white">{c.author.split(" ").map((p) => p[0]).slice(0, 2).join("")}</span>
                  <div className={cn("max-w-[85%] rounded-2xl px-4 py-3", c.mine ? "bg-port text-white" : "bg-alice/80")}>
                    <p className={cn("text-xs font-semibold", c.mine ? "text-white/80" : "text-ink-soft")}>{c.author} <span className="font-normal opacity-80">{c.org_name}{c.party_role ? `, ${c.party_role}` : ""}, {timeAgo(c.created_at)}</span></p>
                    <p className="mt-1 whitespace-pre-wrap text-[15px] leading-snug">{c.body}</p>
                  </div>
                </li>
              ))}
            </ul>
            <form onSubmit={send} className="mt-5 flex gap-2.5">
              <textarea rows={2} className="field-input resize-none" placeholder="Write a message" value={comment} onChange={(e) => setComment(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send(e); }} aria-label="Message" />
              <Button type="submit" loading={sending} disabled={!comment.trim()} aria-label="Send message"><Send className="h-4 w-4" /></Button>
            </form>
          </Card>
        </div>

        <div className="space-y-6 xl:sticky xl:top-8">
          <Card className="p-6">
            <SectionTitle title="Who is on this shipment" />
            <ul className="mt-4 space-y-3">
              {ws.participants.map((p) => (
                <li key={p.org_id} className="flex items-start justify-between gap-3 rounded-xl bg-alice/70 p-3.5">
                  <div className="min-w-0"><p className="truncate font-semibold text-ink">{p.org_name}</p><p className="truncate text-xs text-ink-faint">{p.members.join(", ")}</p></div>
                  <div className="flex items-center gap-1.5"><Badge tone={ROLE_TONE[p.party_role]}>{p.owner ? "Owner" : PARTY_LABEL[p.party_role]}</Badge>
                    {owner && !p.owner && <button onClick={() => run(() => api.removeParticipant(Number(id), p.org_id), "Participant removed.")} aria-label={`Remove ${p.org_name}`} className="rounded-md p-1 text-ink-faint hover:bg-signal-red/10 hover:text-signal-red"><Trash2 className="h-4 w-4" /></button>}</div>
                </li>
              ))}
            </ul>
            {ws.pending_invitations.length > 0 && <div className="mt-3 text-sm text-ink-soft"><p className="font-semibold">Pending invitations</p>{ws.pending_invitations.map((p) => <p key={p.id}>{p.email} as {p.party_role}</p>)}</div>}
            {owner && (
              <form onSubmit={invite} className="mt-5 space-y-2.5 border-t border-alice-200 pt-4">
                <p className="flex items-center gap-2 text-sm font-semibold text-ink"><UserPlus className="h-4 w-4 text-port" /> Invite a partner</p>
                <input className="field-input !py-2" type="email" placeholder="partner@company.com" value={inv.email} onChange={(e) => setInv({ ...inv, email: e.target.value })} disabled={!ws.can_invite} aria-label="Partner email" />
                <div className="flex gap-2"><select className="field-input !py-2" value={inv.role} onChange={(e) => setInv({ ...inv, role: e.target.value as PartyRole })} aria-label="Partner role">{ROLES.map((r) => <option key={r} value={r}>{PARTY_LABEL[r]}</option>)}</select>
                  <Button type="submit" size="sm" loading={inviting} disabled={!ws.can_invite || !inv.email}>Invite</Button></div>
                {!ws.can_invite && <p className="text-xs text-[#B54708]">Confirm your email address first (see the banner at the top).</p>}
                {inviteLink && <p className="rounded-xl bg-signal-amber/10 px-3 py-2 text-xs text-[#7A2E0E]">Demo mode shows the link instead of sending email: <a className="break-all font-semibold underline" href={inviteLink}>{inviteLink}</a></p>}
              </form>
            )}
          </Card>
          <Card className="p-6">
            <SectionTitle title="Activity" />
            <ul className="mt-4 space-y-3">
              {ws.activity.length === 0 && <li className="text-sm text-ink-soft">Nothing yet.</li>}
              {ws.activity.map((a) => <li key={a.id} className="flex gap-2.5 text-sm"><MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-port-300" /><div><p className="text-ink">{a.message}</p><p className="text-xs text-ink-faint">{a.actor}, {timeAgo(a.created_at)}</p></div></li>)}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
