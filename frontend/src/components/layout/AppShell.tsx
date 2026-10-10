"use client";
import { AnimatePresence, motion } from "framer-motion";
import { Activity, FlaskConical, LayoutDashboard, LogOut, MailWarning, Menu, PackagePlus, Radar, Ship, Users, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Logo, LogoMark } from "@/components/brand/Logo";
import { NotificationBell } from "@/components/layout/NotificationBell";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/control-tower", label: "Control Tower", icon: Activity },
  { href: "/shipments", label: "Shipments", icon: Ship },
  { href: "/radar", label: "Radar", icon: Radar },
  { href: "/shipments/new", label: "New shipment", icon: PackagePlus },
  { href: "/team", label: "Team", icon: Users },
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const active = (href: string) => (href === "/shipments" ? pathname === "/shipments" || /^\/shipments\/\d+/.test(pathname) : pathname === href);
  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-gradient-to-b from-prussian via-[#061a45] to-[#0A2A74] text-white">
      <div className="pointer-events-none absolute -left-24 top-1/3 h-72 w-72 rounded-full bg-port/30 blur-[100px]" />
      <div className="relative px-6 pb-4 pt-7"><Logo dark /></div>
      <nav className="relative mt-4 flex-1 space-y-1 px-3">
        {NAV.map((n) => (
          <Link key={n.href} href={n.href} onClick={onNavigate} className={cn("group relative flex items-center gap-3 rounded-xl px-3.5 py-3 text-[15px] font-medium transition", active(n.href) ? "text-white" : "text-white/65 hover:bg-white/5 hover:text-white")}>
            {active(n.href) && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-xl bg-gradient-to-r from-port/90 to-port-400/50 shadow-glow" transition={{ type: "spring", stiffness: 380, damping: 32 }} />}
            <n.icon className="relative h-[18px] w-[18px]" />
            <span className="relative">{n.label}</span>
          </Link>
        ))}
      </nav>
      <div className="relative space-y-3 p-4">
        <div className="glass rounded-2xl p-3.5">
          <div className="flex items-center gap-2 text-sm font-semibold"><FlaskConical className="h-4 w-4 text-port-300" /> Demo mode</div>
          <p className="mt-1 text-xs leading-snug text-white/60">AI responses are simulated. No data leaves this server.</p>
        </div>
        <div className="flex items-center gap-3 rounded-2xl bg-white/5 p-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-port to-port-300 text-sm font-bold">
            {user?.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{user?.name}</p>
            <p className="truncate text-xs text-white/55">{user?.org_name || user?.role}</p>
          </div>
          <NotificationBell dark />
          <button onClick={logout} aria-label="Sign out" className="rounded-lg p-2 text-white/60 transition hover:bg-white/10 hover:text-white"><LogOut className="h-4 w-4" /></button>
        </div>
      </div>
    </div>
  );
}

function VerifyBanner() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  async function resend() {
    setBusy(true);
    try {
      const r = await api.resendVerification();
      if (r.dev_link) window.location.href = r.dev_link; // demo mode: no inbox, so open the link directly
      else toast("Verification email sent. Check your inbox.", "success");
    } catch (e) { toast(e instanceof Error ? e.message : "Could not send the email.", "error"); } finally { setBusy(false); }
  }
  return (
    <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-signal-amber/30 bg-signal-amber/[.08] px-4 py-3 text-sm text-[#7A2E0E]">
      <span className="flex items-center gap-2 font-medium"><MailWarning className="h-4 w-4" /> Confirm your email to invite partners and teammates.</span>
      <button onClick={resend} disabled={busy} className="font-semibold underline disabled:opacity-60">{busy ? "Sending..." : "Send confirmation"}</button>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);
  useEffect(() => setOpen(false), [pathname]);

  if (loading || !user) {
    return (
      <div className="ocean-bg grid min-h-screen place-items-center">
        <LogoMark size={56} className="animate-bob" />
      </div>
    );
  }

  return (
    <div className="min-h-screen lg:pl-[272px]">
      <aside className="no-print fixed inset-y-0 left-0 z-30 hidden w-[272px] lg:block"><SidebarContent /></aside>
      <header className="no-print sticky top-0 z-20 flex items-center justify-between border-b border-alice-200 bg-white/85 px-4 py-3 backdrop-blur lg:hidden">
        <Logo />
        <div className="flex items-center gap-1"><NotificationBell /></div>
        <button onClick={() => setOpen(true)} aria-label="Open menu" className="rounded-lg p-2 text-ink hover:bg-alice-100"><Menu className="h-5 w-5" /></button>
      </header>
      <AnimatePresence>
        {open && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)} className="fixed inset-0 z-40 bg-prussian/60 backdrop-blur-sm lg:hidden" />
            <motion.aside initial={{ x: -300 }} animate={{ x: 0 }} exit={{ x: -300 }} transition={{ type: "spring", stiffness: 340, damping: 34 }} className="fixed inset-y-0 left-0 z-50 w-[272px] lg:hidden">
              <SidebarContent onNavigate={() => setOpen(false)} />
              <button onClick={() => setOpen(false)} aria-label="Close menu" className="absolute right-3 top-6 rounded-lg p-2 text-white/70 hover:bg-white/10"><X className="h-5 w-5" /></button>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
      <main className="mx-auto w-full max-w-[1320px] px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
        {!user.email_verified && <VerifyBanner />}
        {children}
      </main>
    </div>
  );
}
