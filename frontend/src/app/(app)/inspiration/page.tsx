"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";

import { PostCard } from "@/components/inspiration/PostCard";
import { SearchForm } from "@/components/inspiration/SearchForm";
import { useInspirationAccounts, useSearchInspiration } from "@/hooks/useInspiration";

export default function InspirationPage() {
  const accountsQuery = useInspirationAccounts();
  const searchMutation = useSearchInspiration();

  const [username, setUsername] = useState("");
  const [minLikes, setMinLikes] = useState(200);
  const [keyword, setKeyword] = useState("");

  const posts = useMemo(() => searchMutation.data?.posts || [], [searchMutation.data]);

  const handleSubmit = async () => {
    try {
      await searchMutation.mutateAsync({
        username,
        min_likes: minLikes,
        keyword,
        limit: 30,
      });
      toast.success("Search complete");
    } catch {
      toast.error("Search failed");
    }
  };

  return (
    <div className="space-y-5">
      <header className="surface-glow rounded-3xl px-5 py-5 md:px-6 md:py-6">
        <h2 className="font-display text-3xl leading-tight">Inspiration</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">Find high-engagement posts to reuse as sources.</p>
      </header>

      <SearchForm
        accounts={accountsQuery.data || []}
        username={username}
        setUsername={setUsername}
        minLikes={minLikes}
        setMinLikes={setMinLikes}
        keyword={keyword}
        setKeyword={setKeyword}
        onSubmit={handleSubmit}
        loading={searchMutation.isPending}
      />

      {searchMutation.isPending ? (
        <p className="text-sm text-[var(--muted)]">Searching...</p>
      ) : posts.length === 0 ? (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-4 py-5 text-sm text-[var(--muted)]">
          No posts yet. Run a search.
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {posts
            .slice()
            .sort((a, b) => b.likes - a.likes)
            .map((post) => (
              <PostCard key={post.id} post={post} />
            ))}
        </div>
      )}
    </div>
  );
}
