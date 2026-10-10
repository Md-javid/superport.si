"use client";
import { BadgeCheck, ExternalLink, Globe, Landmark } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { WebSource } from "@/lib/types";

const TRUST = {
  official: { label: "Official source", tone: "green" as const, icon: Landmark },
  reference: { label: "Reference site", tone: "blue" as const, icon: BadgeCheck },
  web: { label: "General web", tone: "gray" as const, icon: Globe },
};

function host(url: string) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; }
}

/** Reusable list of web evidence. Every item links to its source. */
export function EvidenceList({ sources, mode }: { sources: WebSource[]; mode?: "live" | "fixture" | "none" }) {
  if (!sources.length) return null;
  return (
    <div>
      {mode === "fixture" && (
        <p className="mb-3 rounded-xl bg-signal-amber/10 px-3.5 py-2.5 text-[13px] font-medium text-[#93370D]">Sample evidence. These are not real search results (fixtures mode).</p>
      )}
      <ul className="space-y-3">
        {sources.map((s) => {
          const t = TRUST[s.trust];
          return (
            <li key={s.url} className="rounded-xl border border-alice-200 p-3.5">
              <div className="flex items-start justify-between gap-3">
                <p className="min-w-0 text-sm font-semibold text-ink"><span className="mr-1.5 text-ink-faint">[{s.index}]</span>{s.title || host(s.url)}</p>
                <Badge tone={t.tone}><t.icon className="h-3 w-3" />{t.label}</Badge>
              </div>
              {s.snippet && <p className="mt-1.5 text-[13px] leading-snug text-ink-soft">{s.snippet}</p>}
              <a href={s.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-port hover:text-port-600">
                {host(s.url)} <ExternalLink className="h-3 w-3" />
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
