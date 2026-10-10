"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PARTY_LABEL, type InvitationInfo, type PartyRole } from "@/lib/types";

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const toast = useToast();
  const { user, loading, logout } = useAuth();
  const [info, setInfo] = useState<InvitationInfo | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.invitation(token).then(setInfo).catch((e) => setError(e.message)); }, [token]);

  async function accept() {
    setBusy(true);
    try { const r = await api.acceptInvitation(token); toast("You joined the shipment.", "success"); router.replace(`/shipments/${r.shipment_id}/workspace`); }
    catch (e) { toast(e instanceof Error ? e.message : "Could not accept.", "error"); setBusy(false); }
  }
  const mismatch = !!(user && info && user.email.toLowerCase() !== info.email.toLowerCase());
  return (
    <AuthShell title="You are invited" subtitle={error || (info ? `${info.inviter_org} invited ${info.email}${info.shipment_reference ? ` to shipment ${info.shipment_reference} as ${PARTY_LABEL[info.party_role as PartyRole].toLowerCase()}` : " to join their team"}.` : "Loading...")}>
      {info && !loading && (
        <div className="space-y-3">
          {user && !mismatch && info.kind === "shipment" && <Button size="lg" className="w-full" onClick={accept} loading={busy}>Join the shipment</Button>}
          {user && mismatch && (<><p className="rounded-xl bg-signal-amber/10 px-4 py-3 text-sm text-[#7A2E0E]">You are signed in as {user.email}, but this invitation is for {info.email}.</p><Button variant="secondary" size="lg" className="w-full" onClick={logout}>Sign out and continue</Button></>)}
          {!user && (<>
            <Link href={`/register?invite=${token}`}><Button size="lg" className="w-full">Create an account</Button></Link>
            {info.kind === "shipment" && <Link href={`/login?next=/invite/${token}`}><Button variant="secondary" size="lg" className="w-full">I already have an account</Button></Link>}
          </>)}
        </div>
      )}
      {error && <Link href="/login" className="font-semibold text-port">Go to sign in</Link>}
    </AuthShell>
  );
}
