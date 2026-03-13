"use client";

import { useSessionStatus } from "@/hooks/useSessionStatus";

export function SessionStatus() {
  const { data, isLoading } = useSessionStatus();

  if (isLoading || !data) return null;
  if (data.status === "valid") return null;

  const styles: Record<string, string> = {
    warning: "border-yellow-500/30 bg-yellow-500/10 text-yellow-200",
    expired: "border-red-500/30 bg-red-500/10 text-red-200",
    missing: "border-red-500/30 bg-red-500/10 text-red-200",
  };

  const color = styles[data.status] || styles.missing;

  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${color}`}>
      <strong>X Session:</strong> {data.message}
    </div>
  );
}
