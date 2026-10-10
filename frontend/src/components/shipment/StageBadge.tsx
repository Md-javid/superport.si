import { Badge, type Tone } from "@/components/ui/Badge";
import type { RiskLevel, Stage } from "@/lib/types";

const STAGE_TONE: Record<Stage, Tone> = { draft: "gray", documents: "gray", extraction_review: "blue", hs_review: "blue", final_review: "amber", ready: "green", rejected: "red" };

export function StageBadge({ stage, label }: { stage: Stage; label: string }) {
  return <Badge tone={STAGE_TONE[stage]} dot>{label}</Badge>;
}

export function RiskBadge({ level, score }: { level: RiskLevel | null; score?: number | null }) {
  if (!level) return <span className="text-sm text-ink-faint">Not scored yet</span>;
  const tone = { low: "green", medium: "amber", high: "red" }[level] as Tone;
  const name = { low: "Low", medium: "Medium", high: "High" }[level];
  return <Badge tone={tone} dot>{name}{score != null ? ` (${score})` : ""}</Badge>;
}
