"use client";

import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export function HebrewEditor({
  value,
  onChange,
  scheduleAt,
  onScheduleAt,
  onCopy,
  onSaveDraft,
  onSchedule,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  scheduleAt: string;
  onScheduleAt: (value: string) => void;
  onCopy: () => void;
  onSaveDraft: () => void;
  onSchedule: () => void;
  disabled?: boolean;
}) {
  const chars = value.length;
  const overLimit = chars > 280;
  const progress = Math.min(100, Math.round((chars / 280) * 100));
  const inputValue = useMemo(() => {
    if (!scheduleAt) {
      return "";
    }
    return scheduleAt.slice(0, 16);
  }, [scheduleAt]);

  return (
    <div className="space-y-3.5">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg">Hebrew Editor</h3>
        <p className={`text-xs ${overLimit ? "text-[var(--danger)]" : "text-[var(--muted)]"}`}>{chars}/280</p>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[rgba(255,255,255,0.08)]">
        <div
          className={`h-full rounded-full transition-[width] duration-300 ${overLimit ? "bg-[var(--danger)]" : "bg-[var(--accent)]"}`}
          style={{ width: `${progress}%` }}
        />
      </div>

      <Textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        dir="rtl"
        className="min-h-[220px] text-base leading-8"
      />
      <p className="text-xs text-[var(--muted)]">Keep it concise, factual, and aligned with your publishing tone guide.</p>

      <div className="grid gap-2 md:grid-cols-[1fr_auto_auto_auto]">
        <Input
          type="datetime-local"
          value={inputValue}
          onChange={(event) => onScheduleAt(event.target.value)}
          className="text-left"
          dir="ltr"
        />
        <Button type="button" variant="secondary" onClick={onCopy} disabled={disabled || !value.trim()}>
          Copy
        </Button>
        <Button type="button" variant="secondary" onClick={onSaveDraft} disabled={disabled || !value.trim()}>
          Save Draft
        </Button>
        <Button type="button" onClick={onSchedule} disabled={disabled || !value.trim()}>
          Schedule
        </Button>
      </div>
    </div>
  );
}
