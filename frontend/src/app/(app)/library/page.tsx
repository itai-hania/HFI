"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ContentCard } from "@/components/queue/ContentCard";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useCopyContent, useDeleteContent, useUpdateContent } from "@/hooks/useContent";
import { useLibrary } from "@/hooks/useLibrary";
import type { ContentItem } from "@/lib/types";

export default function LibraryPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [contentType, setContentType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const query = useLibrary({ search, status, page: 1, limit: 100 });
  const copyMutation = useCopyContent();
  const deleteMutation = useDeleteContent();
  const updateMutation = useUpdateContent();

  const filtered = useMemo(() => {
    return (query.data?.items || []).filter((item) => {
      if (contentType && item.content_type !== contentType) return false;
      if (dateFrom && new Date(item.created_at) < new Date(dateFrom)) return false;
      if (dateTo && new Date(item.created_at) > new Date(dateTo)) return false;
      return true;
    });
  }, [query.data?.items, contentType, dateFrom, dateTo]);

  const handleCopy = async (item: ContentItem) => {
    await navigator.clipboard.writeText(item.hebrew_draft || item.original_text);
    await copyMutation.mutateAsync(item.id);
    toast.success("Copied");
  };

  const handleDelete = async (item: ContentItem) => {
    await deleteMutation.mutateAsync(item.id);
    toast.success("Deleted");
  };

  const handleReschedule = async (item: ContentItem) => {
    const next = window.prompt("Enter ISO datetime (YYYY-MM-DDTHH:mm)", item.scheduled_at?.slice(0, 16) || "");
    if (!next) return;
    await updateMutation.mutateAsync({
      id: item.id,
      payload: { scheduled_at: new Date(next).toISOString(), status: "approved" },
    });
    toast.success("Rescheduled");
  };

  return (
    <div className="space-y-5">
      <header className="surface-glow rounded-3xl px-5 py-5 md:px-6 md:py-6">
        <h2 className="font-display text-3xl leading-tight">Content Library</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">Search and reuse previous content.</p>
      </header>

      <div className="rounded-3xl border border-[var(--border)] bg-[var(--card)]/60 p-4 md:p-5">
        <div className="grid gap-2 md:grid-cols-5">
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search" />
          <Select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All status</option>
            <option value="pending">pending</option>
            <option value="processed">processed</option>
            <option value="approved">approved</option>
            <option value="published">published</option>
          </Select>
          <Select value={contentType} onChange={(event) => setContentType(event.target.value)}>
            <option value="">All types</option>
            <option value="translation">translation</option>
            <option value="generation">generation</option>
            <option value="original">original</option>
          </Select>
          <Input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
          <Input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
        </div>
      </div>

      {query.isLoading ? (
        <p className="text-sm text-[var(--muted)]">Loading...</p>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-4 py-5 text-sm text-[var(--muted)]">
          No results.
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {filtered.map((item) => (
            <ContentCard
              key={item.id}
              item={item}
              onCopy={handleCopy}
              onDelete={handleDelete}
              onReschedule={handleReschedule}
            />
          ))}
        </div>
      )}
    </div>
  );
}
