"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ message: string; dev_link: string | null } | null>(null);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try { setDone(await api.forgotPassword(email)); } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong."); } finally { setBusy(false); }
  }
  return (
    <AuthShell title="Reset your password" subtitle="Enter your email and we will send you a link.">
      {done ? (
        <div className="space-y-4">
          <p className="rounded-xl bg-signal-green/10 px-4 py-3 text-sm font-medium text-[#05603A]">{done.message}</p>
          {done.dev_link && <p className="rounded-xl bg-signal-amber/10 px-4 py-3 text-sm text-[#7A2E0E]">Direct password reset link: <a className="font-semibold underline" href={done.dev_link}>open the reset link</a></p>}
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" noValidate>
          <label className="block"><span className="field-label">Email</span><input className="field-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></label>
          {error && <p role="alert" className="text-sm font-medium text-signal-red">{error}</p>}
          <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!email}>Send reset link</Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm"><Link href="/login" className="font-semibold text-port">Back to sign in</Link></p>
    </AuthShell>
  );
}
