"use client";

import { cn } from "@/lib/utils";

export interface TabItem {
  key: string;
  label: string;
}

export function Tabs({
  tabs,
  active,
  onChange,
  label = "Tabs",
}: {
  tabs: TabItem[];
  active: string;
  onChange: (key: string) => void;
  label?: string;
}) {
  return (
    <div className="inline-flex rounded-2xl border border-[var(--border)] bg-[var(--card)] p-1" role="tablist" aria-label={label}>
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onChange(tab.key)}
          role="tab"
          aria-selected={active === tab.key}
          className={cn(
            "min-h-[44px] cursor-pointer rounded-xl px-4 py-2 text-sm transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
            active === tab.key
              ? "bg-[var(--accent)] text-[var(--accent-ink)] shadow-[0_8px_24px_rgba(29,155,240,0.28)]"
              : "text-[var(--muted)] hover:bg-[var(--card-hover)] hover:text-[var(--ink)]",
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
