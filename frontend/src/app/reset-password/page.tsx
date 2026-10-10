"use client";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => setToken(new URLSearchParams(window.location.search).get("token") ?? ""), []);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try { await api.resetPassword(token, password); setDone(true); } catch (err) { setError(err instanceof Error ? err.message : "Could not reset the password."); } finally { setBusy(false); }
  }
  return (
    <AuthShell title="Choose a new password">
      {done ? (
        <div className="space-y-4"><p className="rounded-xl bg-signal-green/10 px-4 py-3 text-sm font-medium text-[#05603A]">Password updated.</p><Link href="/login" className="font-semibold text-port">Sign in</Link></div>
      ) : (
        <form onSubmit={submit} className="space-y-4" noValidate>
          <label className="block"><span className="field-label">New password</span><input className="field-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" placeholder="8+ characters, a letter and a number" /></label>
          {error && <p role="alert" className="rounded-xl bg-signal-red/8 px-3.5 py-2.5 text-sm font-medium text-[#B42318]">{error}</p>}
          <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!token || !password}>Update password</Button>
        </form>
      )}
    </AuthShell>
  );
}
