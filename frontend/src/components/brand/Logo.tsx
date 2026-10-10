import { cn } from "@/lib/utils";

export function LogoMark({ size = 36, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" className={className} aria-hidden>
      <defs>
        <linearGradient id="sp-g" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop stopColor="#0E3A9A" />
          <stop offset=".55" stopColor="#185DF1" />
          <stop offset="1" stopColor="#7FB0FF" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="11" fill="url(#sp-g)" />
      <path d="M7 24.5c3.2-5 6.2-5 9.4 0s6.2 5 9.4 0 4.2-3 7.2-3" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M7 31c3.2-4 6.2-4 9.4 0s6.2 4 9.4 0 4.2-2.4 7.2-2.4" fill="none" stroke="#fff" strokeOpacity=".55" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="26" cy="12.5" r="3.4" fill="#fff" />
      <path d="M26 6.5v2" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function Logo({ dark = false, className }: { dark?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className={cn("font-display text-[22px] font-extrabold tracking-tight", dark ? "text-white" : "text-prussian")}>
        Super<span className={dark ? "text-port-300" : "text-port"}>Port</span>
      </span>
    </div>
  );
}
