"use client";
import { motion } from "framer-motion";
import { ArrowRight, Check, Eye, EyeOff, FileCheck2, KeyRound, Lock, Mail, ShieldCheck, Sparkles, UserCheck } from "lucide-react";
import Link from "next/link";
import Script from "next/script";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Logo } from "@/components/brand/Logo";
import { OceanScene } from "@/components/brand/OceanScene";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { getApiBase, getGoogleClientId, setCustomApiUrl, setGoogleClientId } from "@/lib/api";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            auto_select?: boolean;
            cancel_on_tap_outside?: boolean;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: {
              theme?: "outline" | "filled_blue" | "filled_black";
              size?: "large" | "medium" | "small";
              type?: "standard" | "icon";
              text?: "signin_with" | "signup_with" | "continue_with" | "signin";
              shape?: "rectangular" | "pill" | "circle" | "square";
              logo_alignment?: "left" | "center";
              width?: number | string;
              locale?: string;
            }
          ) => void;
          prompt: () => void;
        };
      };
    };
  }
}

const GoogleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden>
    <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.1-2.6-.4-3.9z" />
    <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
    <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
    <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z" />
  </svg>
);

const TRUST = [
  { icon: UserCheck, title: "You approve every decision", text: "AI prepares and recommends. Nothing is final until a person signs off." },
  { icon: FileCheck2, title: "Documents read and cross-checked", text: "Invoice, packing list and bill of lading compared automatically." },
  { icon: ShieldCheck, title: "Complete audit trail", text: "Who changed what, and why, recorded on every shipment." },
];

export default function LoginPage() {
  const router = useRouter();
  const toast = useToast();
  const { user, loading, login, googleLogin, demoLogin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState<"form" | "quick" | "google" | null>(null);
  const [error, setError] = useState("");
  const [customUrl, setCustomUrl] = useState("");
  const [showConfig, setShowConfig] = useState(false);

  // Real Google Sign-In state
  const [googleClientId, setGoogleClientIdState] = useState("");
  const [googleClientIdInput, setGoogleClientIdInput] = useState("");
  const [showGoogleConfig, setShowGoogleConfig] = useState(false);
  const [gsiReady, setGsiReady] = useState(false);
  const googleBtnRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setCustomUrl(window.localStorage.getItem("superport.api_url") || "");
      const cid = getGoogleClientId();
      setGoogleClientIdState(cid);
      setGoogleClientIdInput(cid);
    }
  }, []);

  const initGoogle = useCallback(() => {
    if (typeof window === "undefined" || !window.google?.accounts?.id) return;
    const cid = getGoogleClientId();
    if (!cid) return;

    try {
      window.google.accounts.id.initialize({
        client_id: cid,
        callback: async (response) => {
          if (!response?.credential) return;
          setError("");
          setBusy("google");
          try {
            await googleLogin(response.credential);
            const next = new URLSearchParams(window.location.search).get("next");
            router.replace(next && next.startsWith("/") ? next : "/dashboard");
          } catch (err) {
            setError(err instanceof Error ? err.message : "Google authentication failed.");
            setBusy(null);
          }
        },
        auto_select: false,
        cancel_on_tap_outside: true,
      });

      if (googleBtnRef.current) {
        googleBtnRef.current.innerHTML = "";
        window.google.accounts.id.renderButton(googleBtnRef.current, {
          theme: "outline",
          size: "large",
          width: 380,
          text: "continue_with",
          shape: "rectangular",
          logo_alignment: "center",
        });
      }
    } catch (err) {
      console.warn("Failed to initialize Google Sign-In:", err);
    }
  }, [googleLogin, router]);

  useEffect(() => {
    if (googleClientId && gsiReady) {
      initGoogle();
    }
  }, [googleClientId, gsiReady, initGoogle]);

  function onConnectBackend() {
    const trimmed = customUrl.trim();
    if (!trimmed) {
      setCustomApiUrl("");
      toast("Reset backend URL to default proxy", "info");
    } else {
      setCustomApiUrl(trimmed);
      toast("API URL saved. Ready to sign in!", "success");
      setError("");
    }
    setShowConfig(false);
  }

  function onSaveGoogleClientId() {
    const trimmed = googleClientIdInput.trim();
    setGoogleClientId(trimmed);
    setGoogleClientIdState(trimmed);
    if (trimmed) {
      toast("Google Client ID saved. Initializing Google Sign-In...", "success");
      setShowGoogleConfig(false);
      setTimeout(() => initGoogle(), 120);
    } else {
      toast("Google Client ID cleared.", "info");
      if (googleBtnRef.current) googleBtnRef.current.innerHTML = "";
    }
  }

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [user, loading, router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!email || !password) return setError("Enter your email and password to continue.");
    setBusy("form");
    try {
      await login(email, password, remember);
      const next = new URLSearchParams(window.location.search).get("next");
      router.replace(next && next.startsWith("/") ? next : "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed.");
      setBusy(null);
    }
  }

  async function onQuickLogin(persona = "broker") {
    setError("");
    setBusy("quick");
    try {
      await demoLogin(persona);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
      setBusy(null);
    }
  }

  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onLoad={() => {
          setGsiReady(true);
          initGoogle();
        }}
      />
      <main className="grid min-h-screen lg:grid-cols-[1.12fr_1fr]">
        {/* Brand side */}
        <section className="relative isolate flex min-h-[420px] flex-col justify-between overflow-hidden p-8 text-white lg:min-h-screen lg:p-14">
          <OceanScene />
          <Logo dark />
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }} className="relative z-10 my-12 max-w-xl lg:my-0">
            <div className="glass mb-6 inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-medium text-white/90">
              <Sparkles className="h-4 w-4 text-port-300" /> AI customs copilot
            </div>
            <h1 className="font-display text-[44px] font-extrabold leading-[1.05] tracking-tight sm:text-6xl">
              <span className="ocean-text">Intelligence for Global Trade</span>
            </h1>
            <p className="mt-5 max-w-md text-lg leading-relaxed text-white/75">
              SuperPort reads your shipping documents, flags what needs attention, and prepares clearance while you stay in control.
            </p>
          </motion.div>
          <div className="relative z-10 hidden gap-3 lg:grid lg:grid-cols-3">
            {TRUST.map((t, i) => (
              <motion.div key={t.title} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 + i * 0.12, duration: 0.7 }} className="glass rounded-2xl p-4">
                <t.icon className="mb-3 h-5 w-5 text-port-300" />
                <p className="text-sm font-semibold">{t.title}</p>
                <p className="mt-1 text-[13px] leading-snug text-white/65">{t.text}</p>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Form side */}
        <section className="relative flex items-center justify-center bg-gradient-to-b from-white via-alice to-alice-100 px-6 py-12">
          <div className="pointer-events-none absolute right-0 top-0 h-72 w-72 rounded-full bg-port/10 blur-[90px]" />
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.15 }} className="relative w-full max-w-[420px]">
            <h2 className="font-display text-3xl font-bold text-prussian">Welcome back</h2>
            <p className="mt-2 text-ink-soft">Sign in to continue to your shipments.</p>

            <form onSubmit={onSubmit} className="mt-8 space-y-4" noValidate>
              <label className="block">
                <span className="field-label">Work email</span>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
                  <input className="field-input pl-10" type="email" autoComplete="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
                </div>
              </label>
              <label className="block">
                <span className="field-label">Password</span>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
                  <input className="field-input px-10" type={show ? "text" : "password"} autoComplete="current-password" placeholder="Enter your password" value={password} onChange={(e) => setPassword(e.target.value)} />
                  <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-ink-faint hover:text-port">
                    {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </label>
              <div className="flex items-center justify-between text-sm">
                <label className="flex cursor-pointer items-center gap-2 text-ink-soft">
                  <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-4 w-4 rounded border-alice-200 accent-port" />
                  Remember me
                </label>
                <Link href="/forgot-password" className="font-semibold text-port hover:text-port-600">Forgot password?</Link>
              </div>
              {error && (
                <div className="space-y-3">
                  <p role="alert" className="rounded-xl bg-signal-red/8 px-3.5 py-2.5 text-sm font-medium text-[#B42318] ring-1 ring-signal-red/20">{error}</p>
                  {(error.toLowerCase().includes("backend") || error.toLowerCase().includes("cannot reach") || error.includes("404") || showConfig) && (
                    <div className="rounded-2xl border border-port/25 bg-white/95 p-4 text-xs shadow-subtle backdrop-blur">
                      <p className="font-bold text-prussian">Connect Live Render Backend</p>
                      <p className="mt-1 text-ink-soft">Paste your deployed Render URL (e.g. <code className="font-mono text-port">https://your-api.onrender.com</code>) to connect immediately:</p>
                      <div className="mt-2.5 flex gap-2">
                        <input
                          type="url"
                          placeholder="https://your-backend.onrender.com"
                          value={customUrl}
                          onChange={(e) => setCustomUrl(e.target.value)}
                          className="flex-1 rounded-xl border border-alice-300 bg-white px-3 py-2 text-xs text-ink placeholder:text-ink-faint focus:border-port focus:outline-none focus:ring-1 focus:ring-port"
                        />
                        <button
                          type="button"
                          onClick={onConnectBackend}
                          className="rounded-xl bg-port px-3.5 py-2 text-xs font-bold text-white transition hover:bg-port-600 active:scale-95"
                        >
                          Connect
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
              <Button type="submit" size="lg" className="w-full" loading={busy === "form"}>
                Continue <ArrowRight className="h-4 w-4" />
              </Button>
            </form>

            <div className="my-6 flex items-center gap-3 text-xs text-ink-faint">
              <span className="h-px flex-1 bg-alice-200" /> or <span className="h-px flex-1 bg-alice-200" />
            </div>

            {/* Real Google Login Section */}
            <div className="w-full">
              {googleClientId ? (
                <div className="flex flex-col items-center gap-2">
                  <div
                    ref={googleBtnRef}
                    className={`min-h-[44px] w-full flex justify-center transition ${busy === "google" ? "opacity-50 pointer-events-none" : ""}`}
                  />
                  {busy === "google" && (
                    <p className="text-xs font-semibold text-port animate-pulse flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5 animate-spin" /> Verifying Google Account...
                    </p>
                  )}
                  <div className="flex items-center gap-2 pt-1 text-[11px] text-ink-faint">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    <span>Google OAuth ready</span>
                    <span>&bull;</span>
                    <button
                      type="button"
                      onClick={() => setShowGoogleConfig((s) => !s)}
                      className="text-ink-faint hover:text-port transition underline"
                    >
                      {showGoogleConfig ? "Hide Client ID" : "Config"}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <button
                    type="button"
                    onClick={() => setShowGoogleConfig((s) => !s)}
                    disabled={busy !== null}
                    className="flex w-full items-center justify-center gap-3 rounded-xl border border-alice-300 bg-white px-4 py-3 text-sm font-semibold text-prussian shadow-subtle transition hover:bg-alice-50 hover:border-port/40 active:scale-[0.99] disabled:opacity-60"
                  >
                    <GoogleIcon />
                    <span>Continue with Google</span>
                  </button>
                  <p className="text-center text-[11px] text-ink-faint">
                    Google OAuth client credentials required.{" "}
                    <button
                      type="button"
                      onClick={() => setShowGoogleConfig((s) => !s)}
                      className="font-medium text-port hover:underline"
                    >
                      {showGoogleConfig ? "Close setup" : "Set Client ID"}
                    </button>
                  </p>
                </div>
              )}

              {/* Google Client ID Setup Drawer */}
              {showGoogleConfig && (
                <motion.div
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-3 rounded-2xl border border-port/25 bg-white/95 p-4 text-xs shadow-subtle backdrop-blur"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-prussian flex items-center gap-1.5">
                      <KeyRound className="h-3.5 w-3.5 text-port" /> Google OAuth 2.0 Web Client
                    </span>
                    {googleClientId && (
                      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-emerald-600/20">
                        Active
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-ink-soft">
                    Paste your Google OAuth Client ID (from Google Cloud Console &rarr; APIs &amp; Services &rarr; Credentials):
                  </p>
                  <div className="mt-2.5 flex gap-2">
                    <input
                      type="text"
                      placeholder="123456789-xxx.apps.googleusercontent.com"
                      value={googleClientIdInput}
                      onChange={(e) => setGoogleClientIdInput(e.target.value)}
                      className="flex-1 rounded-xl border border-alice-300 bg-white px-3 py-2 text-xs font-mono text-ink placeholder:text-ink-faint focus:border-port focus:outline-none focus:ring-1 focus:ring-port"
                    />
                    <button
                      type="button"
                      onClick={onSaveGoogleClientId}
                      className="rounded-xl bg-port px-3.5 py-2 text-xs font-bold text-white transition hover:bg-port-600 active:scale-95 flex items-center gap-1"
                    >
                      <Check className="h-3.5 w-3.5" /> Save
                    </button>
                  </div>
                  <p className="mt-2 text-[10px] text-ink-faint leading-tight">
                    Tip: Set <code className="font-mono text-port font-semibold">NEXT_PUBLIC_GOOGLE_CLIENT_ID</code> in environment variables or enter it above.
                  </p>
                </motion.div>
              )}
            </div>

            <button onClick={() => onQuickLogin()} disabled={busy !== null} className="group mt-4 flex w-full items-center justify-between rounded-2xl border border-port/25 bg-port-50/70 px-4 py-3.5 text-left transition hover:border-port hover:shadow-glow disabled:opacity-60">
              <span className="flex items-center gap-3">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-port text-white"><Sparkles className="h-4 w-4" /></span>
                <span>
                  <span className="block text-sm font-bold text-prussian">{busy === "quick" ? "Opening workspace..." : "Explore as Customs Broker"}</span>
                  <span className="block text-xs text-ink-soft">Pre-configured workspace with trade shipments</span>
                </span>
              </span>
              <ArrowRight className="h-4 w-4 text-port transition group-hover:translate-x-1" />
            </button>

            <div className="mt-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-sm">
              <span className="text-ink-faint">See it as a partner:</span>
              <button onClick={() => onQuickLogin("forwarder")} className="font-semibold text-port hover:text-port-600">Freight forwarder</button>
              <button onClick={() => onQuickLogin("importer")} className="font-semibold text-port hover:text-port-600">Importer</button>
            </div>
            <div className="mt-3 flex justify-center">
              <button
                type="button"
                onClick={() => setShowConfig((s) => !s)}
                className="text-xs text-ink-faint hover:text-port transition"
              >
                {showConfig ? "Hide backend settings" : "⚙️ Change API Server URL"}
              </button>
            </div>
            {showConfig && !error && (
              <div className="mt-2 rounded-2xl border border-port/25 bg-white/95 p-4 text-xs shadow-subtle backdrop-blur">
                <p className="font-bold text-prussian">Live Backend URL</p>
                <p className="mt-1 text-ink-soft">Current endpoint: <code className="font-mono text-port">{getApiBase()}</code></p>
                <div className="mt-2.5 flex gap-2">
                  <input
                    type="url"
                    placeholder="https://your-backend.onrender.com"
                    value={customUrl}
                    onChange={(e) => setCustomUrl(e.target.value)}
                    className="flex-1 rounded-xl border border-alice-300 bg-white px-3 py-2 text-xs text-ink placeholder:text-ink-faint focus:border-port focus:outline-none focus:ring-1 focus:ring-port"
                  />
                  <button
                    type="button"
                    onClick={onConnectBackend}
                    className="rounded-xl bg-port px-3.5 py-2 text-xs font-bold text-white transition hover:bg-port-600 active:scale-95"
                  >
                    Save
                  </button>
                </div>
              </div>
            )}
            <p className="mt-5 text-center text-sm text-ink-soft">New to SuperPort? <Link href="/register" className="font-semibold text-port">Create an account</Link></p>
            <p className="mt-6 text-center text-xs leading-relaxed text-ink-faint">
              Evaluation environment. SuperPort enforces human review prior to customs submission.
            </p>
          </motion.div>
        </section>
      </main>
    </>
  );
}
