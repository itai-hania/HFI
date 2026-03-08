import * as React from "react";

import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "border border-[transparent] bg-gradient-to-br from-[var(--accent-soft)] to-[var(--accent)] text-[var(--accent-ink)] shadow-[0_10px_30px_rgba(236,72,153,0.3)] hover:brightness-110",
  secondary:
    "border border-[var(--border)] bg-[var(--card)] text-[var(--ink)] hover:border-[var(--accent)]/40 hover:bg-[var(--card-hover)]",
  ghost: "border border-[transparent] bg-transparent text-[var(--muted)] hover:bg-[var(--card)] hover:text-[var(--ink)]",
  danger: "border border-[#be123c] bg-[#4c0519] text-[#ffe4e9] hover:bg-[#65091f]",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex h-11 min-w-[44px] cursor-pointer items-center justify-center gap-2 rounded-xl px-4 text-sm font-medium transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)] disabled:pointer-events-none disabled:opacity-60",
          variantClasses[variant],
          className,
        )}
        {...props}
      />
    );
  },
);

Button.displayName = "Button";
