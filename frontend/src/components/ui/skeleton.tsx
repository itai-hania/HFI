import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-xl bg-[rgba(255,255,255,0.09)] motion-reduce:animate-none", className)} />;
}
