"use client";
import { motion } from "framer-motion";
import { Check, Lock } from "lucide-react";
import { cn } from "@/lib/utils";

export const STEPS = ["Documents", "Data review", "HS code", "Compliance", "Risk", "Approval", "Summary"] as const;

export function WorkflowStepper({ focus, max, active, onSelect }: { focus: number; max: number; active: number; onSelect: (i: number) => void }) {
  return (
    <ol className="no-print flex gap-1 overflow-x-auto pb-1 lg:flex-col lg:gap-0 lg:overflow-visible">
      {STEPS.map((label, i) => {
        const done = i < focus && i <= max;
        const locked = i > max;
        const current = i === active;
        return (
          <li key={label} className="relative shrink-0 lg:shrink">
            {i < STEPS.length - 1 && <span className="absolute left-[19px] top-10 hidden h-[calc(100%-24px)] w-px bg-alice-200 lg:block"><motion.span initial={false} animate={{ height: done ? "100%" : "0%" }} transition={{ duration: 0.6 }} className="block w-full bg-port" /></span>}
            <button disabled={locked} onClick={() => onSelect(i)} aria-current={current ? "step" : undefined} className={cn("flex w-full items-center gap-3 rounded-xl px-2 py-2.5 text-left transition", current ? "bg-white shadow-card ring-1 ring-port/20" : "hover:bg-white/70", locked && "cursor-not-allowed opacity-55 hover:bg-transparent")}>
              <span className={cn("relative grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-bold transition", done ? "bg-port text-white" : current ? "brand-gradient text-white shadow-glow" : "bg-alice-100 text-ink-faint ring-1 ring-alice-200")}>
                {done ? <Check className="h-4 w-4" /> : locked ? <Lock className="h-3.5 w-3.5" /> : i + 1}
                {i === focus && !done && <span className="absolute inset-0 rounded-full ring-2 ring-port/40 animate-ring" />}
              </span>
              <span className={cn("text-sm font-semibold", current ? "text-ink" : "text-ink-soft")}>{label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
