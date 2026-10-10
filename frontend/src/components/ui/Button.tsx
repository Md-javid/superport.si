"use client";
import { Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success" | "light";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary: "brand-gradient text-white shadow-glow hover:brightness-110 animate-gradient",
  secondary: "bg-white text-ink border border-alice-200 hover:border-port-300 hover:bg-port-50/60",
  ghost: "text-ink-soft hover:bg-port-50 hover:text-port-600",
  danger: "bg-white text-signal-red border border-signal-red/30 hover:bg-signal-red/5",
  success: "bg-signal-green text-white hover:brightness-105 shadow-[0_10px_30px_-12px_rgba(18,183,106,.7)]",
  light: "bg-white text-prussian shadow-[0_10px_40px_-10px_rgba(255,255,255,.55)] hover:bg-alice",
};
const sizes: Record<Size, string> = { sm: "h-9 px-3.5 text-sm rounded-lg", md: "h-11 px-5 text-[15px] rounded-xl", lg: "h-12 px-6 text-base rounded-xl" };

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, Props>(function Button({ variant = "primary", size = "md", loading, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "relative inline-flex items-center justify-center gap-2 overflow-hidden font-semibold transition active:scale-[.98] disabled:opacity-50 disabled:pointer-events-none",
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {variant === "primary" && <span className="pointer-events-none absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-white/25 to-transparent animate-shimmer" />}
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      <span className="relative inline-flex items-center gap-2">{children}</span>
    </button>
  );
});
