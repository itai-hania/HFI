"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { InspirationAccount } from "@/lib/types";

export function SearchForm({
  accounts,
  username,
  setUsername,
  minLikes,
  setMinLikes,
  keyword,
  setKeyword,
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
  onSubmit: () => void;
  loading: boolean;
}) {
  return (
    <div className="rounded-3xl border border-[var(--border)] bg-[var(--card)]/60 p-4 md:p-5">
      <div className="grid gap-3 md:grid-cols-[1.2fr_1fr_1fr_auto]">
        <Select value={username} onChange={(event) => setUsername(event.target.value)}>
          <option value="">Choose account</option>
          {accounts.map((account) => (
            <option key={account.id} value={account.username}>
              @{account.username}
            </option>
          ))}
        </Select>
        <Input
          type="number"
          min={0}
          value={minLikes}
          onChange={(event) => setMinLikes(Number(event.target.value || 0))}
          placeholder="Min likes"
        />
        <Input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="Keyword" />
        <Button onClick={onSubmit} disabled={loading || !username}>
          {loading ? "Searching..." : "Search"}
        </Button>
      </div>
    </div>
  );
}
