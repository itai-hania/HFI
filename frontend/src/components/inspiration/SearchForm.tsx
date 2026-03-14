"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function SearchForm({
  username,
  setUsername,
  minLikes,
  setMinLikes,
  keyword,
  setKeyword,
  since,
  setSince,
  until,
  setUntil,
  onSubmit,
  loading,
}: {
  username: string;
  setUsername: (value: string) => void;
  minLikes: number;
  setMinLikes: (value: number) => void;
  keyword: string;
  setKeyword: (value: string) => void;
  since: string;
  setSince: (value: string) => void;
  until: string;
  setUntil: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
}) {
  return (
    <div className="rounded-3xl border border-[var(--border)] bg-[var(--card)]/60 p-4 md:p-5 space-y-3">
      <div className="grid gap-3 md:grid-cols-[1.2fr_0.7fr_0.8fr_0.8fr_1fr_auto]">
        <Input
          value={username}
          onChange={(event) => setUsername(event.target.value.replace(/^@/, ""))}
          placeholder="@username"
          aria-label="Username"
        />
        <Input
          type="number"
          min={0}
          value={minLikes}
          onChange={(event) => setMinLikes(Number(event.target.value || 0))}
          placeholder="Min likes"
          aria-label="Minimum likes"
        />
        <div className="relative">
          <Input
            type="date"
            value={since}
            onChange={(event) => setSince(event.target.value)}
            max={until || undefined}
            aria-label="From date"
          />
          {since && (
            <button
              type="button"
              onClick={() => setSince("")}
              className="absolute right-8 top-1/2 -translate-y-1/2 cursor-pointer rounded-full p-0.5 text-[var(--muted)] hover:text-[var(--ink)] transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              aria-label="Clear from date"
            >
              <X size={12} />
            </button>
          )}
        </div>
        <div className="relative">
          <Input
            type="date"
            value={until}
            onChange={(event) => setUntil(event.target.value)}
            min={since || undefined}
            aria-label="To date"
          />
          {until && (
            <button
              type="button"
              onClick={() => setUntil("")}
              className="absolute right-8 top-1/2 -translate-y-1/2 cursor-pointer rounded-full p-0.5 text-[var(--muted)] hover:text-[var(--ink)] transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              aria-label="Clear to date"
            >
              <X size={12} />
            </button>
          )}
        </div>
        <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="Keyword" aria-label="Keyword" />
        <Button onClick={onSubmit} disabled={loading || !username.trim()}>
          {loading ? "Searching..." : "Search"}
        </Button>
      </div>
    </div>
  );
}
