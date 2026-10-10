"use client";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PARTY_LABEL, type InvitationInfo, type PartyRole } from "@/lib/types";

function RegisterForm() {
  const router = useRouter();
  const toast = useToast();
  const { signUp } = useAuth();
  const [invite, setInvite] = useState<string | null>(null);
  const [info, setInfo] = useState<InvitationInfo | null>(null);
  const [f, setF] = useState({ org_name: "", org_type: "broker" as PartyRole, name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("invite");
    if (!token) return;
    setInvite(token);
    api.invitation(token).then((i) => { setInfo(i); setF((x) => ({ ...x, email: i.email, org_type: i.party_role ?? x.org_type })); }).catch((e) => setError(e.message));
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await signUp({ ...f, invite_token: invite ?? undefined });
      toast(res.joined_shipment_id ? "Welcome. You have joined the shipment." : "Account created. Confirm your email from the banner.", "success");
      router.replace(res.joined_shipment_id ? `/shipments/${res.joined_shipment_id}/workspace` : "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the account.");
      setBusy(false);
    }
  }
  const joiningTeam = info?.kind === "team";
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((x) => ({ ...x, [k]: e.target.value }));
  return (
    <AuthShell title={info ? "Accept your invitation" : "Create your workspace"} subtitle={info ? `${info.inviter_org} invited you${info.shipment_reference ? ` to shipment ${info.shipment_reference} as ${PARTY_LABEL[info.party_role as PartyRole].toLowerCase()}` : " to their team"}.` : "Set up your company and start with your first shipment."}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {!joiningTeam && (
          <label className="block"><span className="field-label">Company name</span><input className="field-input" value={f.org_name} onChange={set("org_name")} placeholder="Your company" /></label>
        )}
        {!info && (
          <label className="block"><span className="field-label">Your company is a</span>
            <select className="field-input" value={f.org_type} onChange={set("org_type")}>{(Object.keys(PARTY_LABEL) as PartyRole[]).map((r) => <option key={r} value={r}>{PARTY_LABEL[r]}</option>)}</select>
          </label>
        )}
        <label className="block"><span className="field-label">Your name</span><input className="field-input" value={f.name} onChange={set("name")} autoComplete="name" /></label>
        <label className="block"><span className="field-label">Work email</span><input className="field-input" type="email" value={f.email} onChange={set("email")} readOnly={!!info} autoComplete="email" /></label>
        <label className="block"><span className="field-label">Password</span><input className="field-input" type="password" value={f.password} onChange={set("password")} autoComplete="new-password" placeholder="8+ characters, a letter and a number" /></label>
        {error && <p role="alert" className="rounded-xl bg-signal-red/8 px-3.5 py-2.5 text-sm font-medium text-[#B42318] ring-1 ring-signal-red/20">{error}</p>}
        <Button type="submit" size="lg" className="w-full" loading={busy}>{info ? "Accept and continue" : "Create account"} <ArrowRight className="h-4 w-4" /></Button>
      </form>
      <p className="mt-6 text-center text-sm text-ink-soft">Already have an account? <Link href={invite ? `/login?next=/invite/${invite}` : "/login"} className="font-semibold text-port">Sign in</Link></p>
    </AuthShell>
  );
}

export default function RegisterPage() {
  return <Suspense fallback={<div className="ocean-bg min-h-screen" />}><RegisterForm /></Suspense>;
}
