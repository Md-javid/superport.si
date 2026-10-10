import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const tones = {
  green: "bg-signal-green/10 text-[#067647] ring-signal-green/25",
  amber: "bg-signal-amber/10 text-[#B54708] ring-signal-amber/30",
  red: "bg-signal-red/10 text-[#B42318] ring-signal-red/25",
  blue: "bg-port-50 text-port-600 ring-port/20",
  navy: "bg-prussian text-white ring-prussian",
  gray: "bg-alice-100 text-ink-soft ring-alice-200",
};
export type Tone = keyof typeof tones;

export function Badge({ tone = "gray", children, className, dot }: { tone?: Tone; children: ReactNode; className?: string; dot?: boolean }) {
  const dotColor = { green: "bg-signal-green", amber: "bg-signal-amber", red: "bg-signal-red", blue: "bg-port", navy: "bg-white", gray: "bg-ink-faint" }[tone];
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset", tones[tone], className)}>
      {dot && <span className={cn("h-1.5 w-1.5 rounded-full", dotColor)} />}
      {children}
    </span>
  );
}
