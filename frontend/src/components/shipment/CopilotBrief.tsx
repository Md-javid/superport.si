"use client";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Compass, HelpCircle, Lightbulb, Sparkles, UserCheck } from "lucide-react";
import type { Brief } from "@/lib/types";

const ROWS: { key: keyof Brief; label: string; icon: typeof Sparkles; tone: string }[] = [
  { key: "happened", label: "What happened", icon: CheckCircle2, tone: "text-port bg-port-50" },
  { key: "why", label: "Why", icon: HelpCircle, tone: "text-prussian-500 bg-alice-100" },
  { key: "recommendation", label: "What AI recommends", icon: Lightbulb, tone: "text-[#B54708] bg-signal-amber/10" },
  { key: "approval", label: "Needs your approval", icon: UserCheck, tone: "text-[#067647] bg-signal-green/10" },
  { key: "next", label: "What happens next", icon: Compass, tone: "text-port-600 bg-port-50" },
];

export function CopilotBrief({ brief, stageKey }: { brief: Brief; stageKey: string }) {
  return (
    <aside className="no-print relative overflow-hidden rounded-2xl border border-alice-200/80 bg-white shadow-card">
      <div className="relative overflow-hidden bg-gradient-to-br from-prussian via-prussian-700 to-port px-5 py-4 text-white">
        <div className="absolute -right-8 -top-10 h-32 w-32 rounded-full bg-port-300/40 blur-3xl animate-aurora" />
        <div className="relative flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-white/15"><Sparkles className="h-4 w-4" /></span>
          <div>
            <p className="font-display text-[15px] font-bold leading-tight">Copilot brief</p>
            <p className="text-xs text-white/65">Short, so you can decide fast</p>
          </div>
        </div>
      </div>
      <AnimatePresence mode="wait">
        <motion.ul key={stageKey} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.28 }} className="space-y-4 p-5">
          {ROWS.map((r) => (
            <li key={r.key} className="flex gap-3">
              <span className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg ${r.tone}`}><r.icon className="h-3.5 w-3.5" /></span>
              <div>
                <p className="text-xs font-semibold text-ink-faint">{r.label}</p>
                <p className="mt-0.5 text-[14px] leading-snug text-ink">{brief[r.key]}</p>
              </div>
            </li>
          ))}
        </motion.ul>
      </AnimatePresence>
    </aside>
  );
}
