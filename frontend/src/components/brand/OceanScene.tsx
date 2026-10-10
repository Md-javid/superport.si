"use client";
import { cn } from "@/lib/utils";

/** Ambient ocean + shipping-lane scene. Pure CSS/SVG, no assets. */
const PORTS = [
  { x: 120, y: 330, label: "Rotterdam" },
  { x: 330, y: 250, label: "Jebel Ali" },
  { x: 520, y: 360, label: "Chennai" },
  { x: 690, y: 270, label: "Shenzhen" },
  { x: 880, y: 210, label: "Busan" },
];
const LANES = [
  "M120 330 C 190 200, 270 190, 330 250",
  "M330 250 C 400 330, 460 380, 520 360",
  "M520 360 C 560 250, 640 220, 690 270",
  "M690 270 C 750 160, 830 150, 880 210",
  "M120 330 C 280 480, 440 470, 520 360",
];

function Wave({ className, fill, opacity, d }: { className: string; fill: string; opacity: number; d: string }) {
  return (
    <div className={cn("absolute bottom-0 left-0 h-[34%] w-[200%]", className)}>
      <svg viewBox="0 0 1440 200" preserveAspectRatio="none" className="h-full w-full" style={{ opacity }}>
        <path d={d} fill={fill} />
      </svg>
    </div>
  );
}

export function OceanScene({ className, lanes = true }: { className?: string; lanes?: boolean }) {
  const wave1 = "M0 90 C 120 40 240 40 360 90 S 600 140 720 90 S 960 40 1080 90 S 1320 140 1440 90 V200 H0Z";
  const wave2 = "M0 120 C 120 80 240 80 360 120 S 600 160 720 120 S 960 80 1080 120 S 1320 160 1440 120 V200 H0Z";
  return (
    <div className={cn("ocean-bg absolute inset-0 overflow-hidden", className)} aria-hidden>
      {/* gradient light */}
      <div className="absolute -left-40 -top-40 h-[620px] w-[620px] rounded-full bg-port/50 blur-[120px] animate-aurora" />
      <div className="absolute right-[-12%] top-[18%] h-[520px] w-[520px] rounded-full bg-[#5FA8FF]/35 blur-[130px] animate-aurora-slow" />
      <div className="absolute bottom-[-10%] left-[22%] h-[420px] w-[620px] rounded-full bg-[#7C6CFF]/25 blur-[120px] animate-aurora" />
      {/* soft grid */}
      <div className="absolute inset-0 opacity-[.18]" style={{ backgroundImage: "radial-gradient(rgba(255,255,255,.9) 1px, transparent 1.2px)", backgroundSize: "26px 26px", maskImage: "radial-gradient(ellipse at 50% 40%, #000 20%, transparent 75%)", WebkitMaskImage: "radial-gradient(ellipse at 50% 40%, #000 20%, transparent 75%)" }} />
      {lanes && (
        <svg viewBox="0 0 1000 520" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 h-full w-full">
          <defs>
            <linearGradient id="lane" x1="0" x2="1">
              <stop offset="0" stopColor="#7FB0FF" stopOpacity="0" />
              <stop offset=".5" stopColor="#BCD3FF" stopOpacity=".95" />
              <stop offset="1" stopColor="#7FB0FF" stopOpacity="0" />
            </linearGradient>
          </defs>
          {LANES.map((d, i) => (
            <g key={d}>
              <path d={d} fill="none" stroke="rgba(188,211,255,.18)" strokeWidth="1.2" />
              <path d={d} fill="none" stroke="url(#lane)" strokeWidth="1.8" strokeLinecap="round" strokeDasharray="10 38" className="animate-dash" style={{ animationDelay: `${i * -0.5}s` }} />
              <circle r="3.2" fill="#fff">
                <animateMotion dur={`${9 + i * 1.7}s`} repeatCount="indefinite" path={d} begin={`${i * -2}s`} />
              </circle>
            </g>
          ))}
          {PORTS.map((p, i) => (
            <g key={p.label} transform={`translate(${p.x} ${p.y})`}>
              <circle r="5" fill="none" stroke="#9CC2FF" strokeWidth="1.5" className="origin-center animate-ring" style={{ transformBox: "fill-box", animationDelay: `${i * 0.5}s` }} />
              <circle r="4.2" fill="#fff" />
              <text x="10" y="4" fontSize="11" fill="rgba(255,255,255,.75)" fontFamily="Inter Variable, sans-serif">{p.label}</text>
            </g>
          ))}
        </svg>
      )}
      <Wave className="animate-wave-slow" fill="#0E3A9A" opacity={0.55} d={wave2} />
      <Wave className="animate-wave" fill="#031130" opacity={0.7} d={wave1} />
    </div>
  );
}
