"use client";
import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { Logo } from "@/components/brand/Logo";
import { OceanScene } from "@/components/brand/OceanScene";

/** Shared layout for sign-up, reset and invitation pages. */
export function AuthShell({ title, subtitle, children, aside }: { title: string; subtitle?: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <main className="grid min-h-screen lg:grid-cols-[1fr_1.05fr]">
      <section className="relative isolate hidden flex-col justify-between overflow-hidden p-12 text-white lg:flex">
        <OceanScene />
        <Logo dark />
        <div className="relative z-10 max-w-md">
          <h2 className="font-display text-4xl font-extrabold leading-tight"><span className="ocean-text">One shared workspace for every shipment</span></h2>
          <p className="mt-4 text-lg leading-relaxed text-white/75">Brokers, forwarders, importers and exporters see the same checklist, the same discussion and the same status. No more WhatsApp threads.</p>
          {aside}
        </div>
        <p className="relative z-10 text-xs text-white/50">Intelligence for Global Trade</p>
      </section>
      <section className="flex items-center justify-center bg-gradient-to-b from-white via-alice to-alice-100 px-6 py-12">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="w-full max-w-[440px]">
          <div className="mb-8 lg:hidden"><Logo /></div>
          <h1 className="font-display text-3xl font-bold text-prussian">{title}</h1>
          {subtitle && <p className="mt-2 text-ink-soft">{subtitle}</p>}
          <div className="mt-7">{children}</div>
        </motion.div>
      </section>
    </main>
  );
}
