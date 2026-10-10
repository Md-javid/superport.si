"use client";
import { motion } from "framer-motion";
import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export const PIPELINE = ["Uploading", "Extracting", "Validating", "Cross-checking", "Ready"] as const;

/** active: index of the running stage; PIPELINE.length means everything is complete. */
export function ProcessingPipeline({ active, detail }: { active: number; detail?: string }) {
  const complete = active >= PIPELINE.length - 1;
  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-prussian via-prussian-700 to-[#0F4BC9] p-6 text-white shadow-lift">
      <div className="absolute -left-10 -top-16 h-52 w-52 rounded-full bg-port/50 blur-3xl animate-aurora" />
      <div className="relative">
        <p className="font-display text-lg font-bold">{complete ? "Analysis complete" : "SuperPort is reading your documents"}</p>
        <p className="mt-1 text-sm text-white/70">{detail ?? (complete ? "Review the extracted data next." : "This takes a few seconds.")}</p>
        <ol className="mt-6 grid gap-3 sm:grid-cols-5">
          {PIPELINE.map((label, i) => {
            const done = i < active || complete;
            const running = i === active && !complete;
            return (
              <li key={label} className="relative">
                <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-white/15">
                  <motion.div initial={false} animate={{ width: done ? "100%" : running ? "62%" : "0%" }} transition={{ duration: running ? 1.4 : 0.4, ease: "easeOut" }} className="h-full rounded-full bg-gradient-to-r from-port-300 to-white" />
                </div>
                <div className="flex items-center gap-2">
                  <span className={cn("grid h-6 w-6 place-items-center rounded-full text-[11px] font-bold transition", done ? "bg-signal-green text-white" : running ? "bg-white text-port" : "bg-white/10 text-white/50")}>
                    {done ? <Check className="h-3.5 w-3.5" /> : running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : i + 1}
                  </span>
                  <span className={cn("text-sm font-semibold", done || running ? "text-white" : "text-white/45")}>{label}</span>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
