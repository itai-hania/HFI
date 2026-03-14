"use client";

import { useMemo, useState } from "react";
import { X } from "lucide-react";
import { toast } from "sonner";

import { PostCard } from "@/components/inspiration/PostCard";
import { SearchForm } from "@/components/inspiration/SearchForm";
import { SessionStatus } from "@/components/SessionStatus";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useInspirationAccounts,
  useAddInspirationAccount,
  useDeleteInspirationAccount,
  useSearchInspiration,
} from "@/hooks/useInspiration";

const PAGE_SIZE = 5;

function toDateInputValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function defaultSince() {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return toDateInputValue(d);
}

function defaultUntil() {
  return toDateInputValue(new Date());
}

export default function InspirationPage() {
  const accountsQuery = useInspirationAccounts();
  const addAccount = useAddInspirationAccount();
  const deleteAccount = useDeleteInspirationAccount();
  const searchMutation = useSearchInspiration();

  const [newUsername, setNewUsername] = useState("");
  const [username, setUsername] = useState("");
  const [minLikes, setMinLikes] = useState(200);
  const [keyword, setKeyword] = useState("");
  const [since, setSince] = useState(defaultSince);
  const [until, setUntil] = useState(defaultUntil);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const posts = useMemo(() => searchMutation.data?.posts || [], [searchMutation.data]);
  const sortedPosts = useMemo(() => [...posts].sort((a, b) => b.likes - a.likes), [posts]);
  const visiblePosts = sortedPosts.slice(0, visibleCount);
  const remaining = sortedPosts.length - visibleCount;

  const handleAddAccount = async () => {
    const cleaned = newUsername.trim().replace(/^@/, "");
    if (!cleaned) return;
    try {
      await addAccount.mutateAsync({ username: cleaned });
      setNewUsername("");
      toast.success(`Added @${cleaned}`);
    } catch {
      toast.error("Failed to add account");
    }
  };

  const handleDeleteAccount = async (id: number, name: string) => {
    try {
      await deleteAccount.mutateAsync(id);
      toast.success(`Removed @${name}`);
    } catch {
      toast.error("Failed to remove account");
    }
  };

  const handleSearch = async () => {
    const cleanedUsername = username.trim().replace(/^@/, "");
    if (!cleanedUsername) {
      toast.error("Enter a username to search");
      return;
    }
    if (since && until && since > until) {
      toast.error("From date must be before to date");
      return;
    }

    setVisibleCount(PAGE_SIZE);
    try {
      await searchMutation.mutateAsync({
        username: cleanedUsername,
        min_likes: minLikes,
        keyword,
        limit: 30,
        since: since || undefined,
        until: until || undefined,
      });
      toast.success("Search complete");
    } catch (error: unknown) {
      const err = error as { response?: { status?: number; data?: { detail?: string } }; message?: string };
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;

      if (!err?.response) {
        toast.error("Cannot reach API server. Check that it is running.");
      } else if (status === 503) {
        toast.error(detail || "X session expired. Refresh the session file on the server.");
      } else if (status === 504) {
        toast.error(detail || "Search timed out. Try again later.");
      } else if (status === 404) {
        toast.error(detail || "Account not tracked. Add it first using the + Add button above.");
      } else {
        toast.error(detail || "Search failed. Check server logs.");
      }
    }
  };

  return (
    <div className="space-y-5">
      <header className="surface-glow rounded-3xl px-5 py-5 md:px-6 md:py-6">
        <h2 className="font-display text-3xl leading-tight">Inspiration</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">Find high-engagement posts to reuse as sources.</p>
      </header>

      <SessionStatus />

      <div className="rounded-3xl border border-[var(--border)] bg-[var(--card)]/60 p-4 md:p-5 space-y-3">
        <div className="flex flex-wrap gap-2">
          <Input
            value={newUsername}
            onChange={(event) => setNewUsername(event.target.value)}
            placeholder="@username"
            className="w-full sm:max-w-xs"
            onKeyDown={(event) => {
              if (event.key === "Enter") handleAddAccount();
            }}
          />
          <Button onClick={handleAddAccount} disabled={addAccount.isPending || !newUsername.trim()}>
            + Add
          </Button>
        </div>

        {(accountsQuery.data || []).length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {(accountsQuery.data || []).map((account) => (
              <span
                key={account.id}
                className="inline-flex items-center gap-1 rounded-full border border-[var(--border)] bg-[rgba(255,255,255,0.04)] px-3 py-1 text-xs text-[var(--muted)]"
              >
                <button
                  type="button"
                  onClick={() => setUsername(account.username)}
                  className="cursor-pointer hover:text-[var(--ink)] transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] rounded-sm"
                  aria-label={`Use @${account.username} in search`}
                >
                  @{account.username}
                </button>
                <button
                  type="button"
                  onClick={() => handleDeleteAccount(account.id, account.username)}
                  className="cursor-pointer rounded-full p-1 hover:bg-[rgba(255,255,255,0.1)] transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                  aria-label={`Remove @${account.username} from tracked accounts`}
                  disabled={deleteAccount.isPending}
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      <SearchForm
        accounts={accountsQuery.data || []}
        username={username}
        setUsername={setUsername}
        minLikes={minLikes}
        setMinLikes={setMinLikes}
        keyword={keyword}
        setKeyword={setKeyword}
        since={since}
        setSince={setSince}
        until={until}
        setUntil={setUntil}
        onSubmit={handleSearch}
        loading={searchMutation.isPending}
      />

      {searchMutation.isPending ? (
        <p className="text-sm text-[var(--muted)]">Searching...</p>
      ) : posts.length === 0 && searchMutation.isSuccess ? (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-4 py-5 text-sm text-[var(--muted)]">
          No posts found matching your criteria. Try lowering the minimum likes or broadening the date range.
        </div>
      ) : posts.length === 0 ? (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-4 py-5 text-sm text-[var(--muted)]">
          Search for high-engagement posts from tracked accounts.
        </div>
      ) : (
        <>
          <div className="grid gap-3 lg:grid-cols-2">
            {visiblePosts.map((post) => (
              <PostCard key={post.id} post={post} />
            ))}
          </div>

          {remaining > 0 && (
            <div className="flex justify-center">
              <Button variant="secondary" onClick={() => setVisibleCount((prev) => prev + PAGE_SIZE)}>
                See more ({remaining} remaining)
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
