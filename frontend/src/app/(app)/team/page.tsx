"use client";
import { MailCheck } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, SectionTitle, Skeleton } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { PARTY_LABEL, type TeamData } from "@/lib/types";

export default function TeamPage() {
  const toast = useToast();
  const [data, setData] = useState<TeamData | null>(null);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<string | null>(null);
  const load = useCallback(() => api.team().then(setData).catch((e) => toast(e.message, "error")), [toast]);
  useEffect(() => { load(); }, [load]);

  async function invite(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try { const r = await api.inviteTeammate(email); setLink(r.dev_link); setEmail(""); toast(`Invitation sent to ${r.email}.`, "success"); await load(); }
    catch (err) { toast(err instanceof Error ? err.message : "Could not send the invitation.", "error"); }
    finally { setBusy(false); }
  }
  if (!data) return <Skeleton className="h-64" />;
  return (
    <div className="space-y-6">
      <div><h1 className="font-display text-3xl font-extrabold text-prussian">{data.org.name}</h1><p className="mt-1 text-ink-soft">{PARTY_LABEL[data.org.type]}. Everyone here sees the same shipments.</p></div>
      <Card className="p-6">
        <SectionTitle title="Members" />
        <ul className="mt-4 divide-y divide-alice-200/70">{data.members.map((m) => (
          <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 py-3"><div><p className="font-semibold text-ink">{m.name}</p><p className="text-sm text-ink-soft">{m.email}</p></div><div className="flex gap-2"><Badge tone={m.org_role === "admin" ? "navy" : "gray"}>{m.org_role}</Badge>{!m.email_verified && <Badge tone="amber">Email not confirmed</Badge>}</div></li>
        ))}</ul>
      </Card>
      <Card className="p-6">
        <SectionTitle title="Invite a teammate" hint={data.can_invite ? "They will join this organisation as a member." : "Only admins with a confirmed email can invite teammates."} />
        <form onSubmit={invite} className="mt-4 flex flex-wrap gap-3">
          <input className="field-input min-w-[240px] flex-1" type="email" placeholder="colleague@company.com" value={email} onChange={(e) => setEmail(e.target.value)} disabled={!data.can_invite} aria-label="Teammate email" />
          <Button type="submit" loading={busy} disabled={!data.can_invite || !email}><MailCheck className="h-4 w-4" /> Send invitation</Button>
        </form>
        {link && <p className="mt-3 rounded-xl bg-signal-amber/10 px-3.5 py-2.5 text-sm text-[#7A2E0E]">Demo mode shows the link instead of sending email: <a className="break-all font-semibold underline" href={link}>{link}</a></p>}
        {data.invitations.length > 0 && <div className="mt-5"><p className="text-sm font-semibold text-ink-soft">Pending</p><ul className="mt-2 space-y-1">{data.invitations.map((i) => <li key={i.id} className="text-sm text-ink">{i.email}</li>)}</ul></div>}
      </Card>
    </div>
  );
}
