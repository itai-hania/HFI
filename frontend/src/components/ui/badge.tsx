import { cn } from "@/lib/utils";

export function Badge({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-[var(--border)] bg-[rgba(255,255,255,0.03)] px-2.5 py-1 text-xs font-medium text-[var(--muted)]",
        className,
      )}
    >
      {children}
    </span>
  );
}
