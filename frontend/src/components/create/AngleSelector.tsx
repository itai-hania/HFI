"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

const ANGLES = [
  { key: "news", label: "News", hint: "Fast updates and key facts" },
  { key: "educational", label: "Educational", hint: "Explainers and practical guidance" },
  { key: "opinion", label: "Opinion", hint: "Point of view and market stance" },
] as const;

export function AngleSelector({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  useEffect(() => {
    const stored = localStorage.getItem("hfi_last_angle");
    if (stored && ANGLES.some((angle) => angle.key === stored) && !value) {
      onChange(stored);
    }
  }, [onChange, value]);

  useEffect(() => {
    if (value) {
      localStorage.setItem("hfi_last_angle", value);
    }
  }, [value]);

  return (
    <div className="space-y-2.5">
      <h3 className="font-display text-lg">Angle</h3>
      <div className="grid gap-2 md:grid-cols-3">
        {ANGLES.map((angle) => (
          <Button
            key={angle.key}
            type="button"
            variant={value === angle.key ? "primary" : "secondary"}
            onClick={() => onChange(angle.key)}
            className="h-auto min-h-[44px] flex-col items-start gap-0.5 py-2 text-right"
          >
            <span>{angle.label}</span>
            <span className={value === angle.key ? "text-[rgba(255,250,252,0.88)]" : "text-[var(--muted)]"}>
              {angle.hint}
            </span>
          </Button>
        ))}
      </div>
    </div>
  );
}
