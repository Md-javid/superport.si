"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthShell } from "@/components/layout/AuthShell";
import { api } from "@/lib/api";

export default function VerifyEmailPage() {
  const [state, setState] = useState<"working" | "ok" | "bad">("working");
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token") ?? "";
    api.verifyEmail(token).then(() => setState("ok")).catch(() => setState("bad"));
  }, []);
  return (
    <AuthShell title={state === "ok" ? "Email confirmed" : state === "bad" ? "Link not valid" : "Confirming your email"}>
      <p className="text-ink-soft">{state === "ok" ? "You can now invite partners to your shipments." : state === "bad" ? "This link is invalid or has expired. Sign in and request a new one from the banner." : "One moment..."}</p>
      {state !== "working" && <Link href="/dashboard" className="mt-6 inline-block font-semibold text-port">Go to SuperPort</Link>}
    </AuthShell>
  );
}
