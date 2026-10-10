"use client";
import { motion } from "framer-motion";
import { Info } from "lucide-react";
import { AnimatedNumber, Card, ProgressBar } from "@/components/ui/Primitives";
import type { Risk } from "@/lib/types";
import { riskColor } from "@/lib/utils";

function Gauge({ score, level }: { score: number; level: Risk["level"] }) {
  const r = 92;
  const len = Math.PI * r;
  const color = riskColor[level];
  return (
    <div className="relative mx-auto w-[260px]">
      <svg viewBox="0 0 220 125" className="w-full overflow-visible">
        <defs>
          <linearGradient id="gauge-track" x1="0" x2="1">
            <stop offset="0" stopColor="#12B76A" stopOpacity=".25" /><stop offset=".45" stopColor="#F79009" stopOpacity=".25" /><stop offset="1" stopColor="#F04438" stopOpacity=".25" />
          </linearGradient>
        </defs>
        <path d="M18 110 A92 92 0 0 1 202 110" fill="none" stroke="url(#gauge-track)" strokeWidth="16" strokeLinecap="round" />
        <motion.path d="M18 110 A92 92 0 0 1 202 110" fill="none" stroke={color} strokeWidth="16" strokeLinecap="round" strokeDasharray={len} initial={{ strokeDashoffset: len }} animate={{ strokeDashoffset: len * (1 - Math.max(score, 2) / 100) }} transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }} style={{ filter: `drop-shadow(0 4px 10px ${color}66)` }} />
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <p className="font-display text-5xl font-extrabold leading-none text-ink"><AnimatedNumber value={score} /><span className="text-xl font-bold text-ink-faint"> / 100</span></p>
      </div>
    </div>
  );
}

export function RiskStep({ risk }: { risk: Risk | null }) {
  if (!risk) return <Card className="p-10 text-center text-ink-soft">The internal risk score is calculated after you confirm the extracted data.</Card>;
  const color = riskColor[risk.level];
  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-2xl font-bold text-ink">Internal risk assessment</h2>
        <p className="mt-1 text-ink-soft">An internal estimate to help you decide where to look. Higher means more review is advisable.</p>
      </div>

      <Card className="overflow-hidden">
        <div className="grid items-center gap-6 p-7 md:grid-cols-[300px_1fr]">
          <Gauge score={risk.score} level={risk.level} />
          <div>
            <p className="text-sm font-medium text-ink-faint">Risk score</p>
            <p className="font-display text-3xl font-extrabold text-ink">{risk.score} / 100</p>
            <p className="mt-2 inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-bold" style={{ background: `${color}1A`, color }}><span className="h-2 w-2 rounded-full" style={{ background: color }} /> Status: {risk.label}</p>
            <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">{risk.headline} The largest contributor is {risk.main_driver.toLowerCase()}.</p>
            <div className="mt-4 flex gap-4 text-xs text-ink-faint">
              {[["#12B76A", "Low, under 30"], ["#F79009", "Medium, 30 to 49"], ["#F04438", "High, 50 and above"]].map(([c, l]) => <span key={l} className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />{l}</span>)}
            </div>
          </div>
        </div>
      </Card>

      <Card className="p-6">
        <h3 className="font-display text-base font-bold text-ink">What drives the score</h3>
        <ul className="mt-5 space-y-5">
          {risk.factors.map((f, i) => (
            <motion.li key={f.key} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}>
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-sm font-semibold text-ink">{f.label} <span className="font-normal text-ink-faint">({Math.round(f.weight * 100)}% of score)</span></p>
                <p className="text-sm font-bold" style={{ color: riskColor[f.level] }}>{f.score}/100</p>
              </div>
              <ProgressBar value={f.score} color={riskColor[f.level]} className="mt-2" height={8} />
              <p className="mt-1.5 text-[13px] text-ink-soft">{f.explanation}</p>
              {f.basis && <p className="mt-0.5 text-xs text-ink-faint">Basis: {f.basis}</p>}
            </motion.li>
          ))}
        </ul>
      </Card>

      <div className="flex gap-3 rounded-2xl border border-alice-200 bg-white p-4 text-sm text-ink-soft">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-port" />
        <p>{risk.disclaimer} The colours here are SuperPort&apos;s own and do not correspond to any customs authority&apos;s channels.</p>
      </div>
    </div>
  );
}
