"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { InspirationAccount } from "@/lib/types";

export function SearchForm({
  accounts,
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
  accounts: InspirationAccount[];
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
      {accounts.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {accounts.map((account) => (
            <button
              key={account.id}
              type="button"
              onClick={() => setUsername(account.username)}
              className="cursor-pointer rounded-full border border-[var(--border)] bg-[rgba(255,255,255,0.04)] px-3 py-1 text-xs text-[var(--muted)] hover:bg-[rgba(255,255,255,0.08)] hover:text-[var(--ink)] transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              aria-label={`Select @${account.username}`}
            >
              @{account.username}
            </button>
          ))}
        </div>
      )}

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
        <Input
          type="date"
          value={since}
          onChange={(event) => setSince(event.target.value)}
          max={until || undefined}
          aria-label="From date"
        />
        <Input
          type="date"
          value={until}
          onChange={(event) => setUntil(event.target.value)}
          min={since || undefined}
          aria-label="To date"
        />
        <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="Keyword" aria-label="Keyword" />
        <Button onClick={onSubmit} disabled={loading || !username.trim()}>
          {loading ? "Searching..." : "Search"}
        </Button>
      </div>
    </div>
  );
}
