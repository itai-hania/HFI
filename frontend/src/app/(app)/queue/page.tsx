"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { ContentCard } from "@/components/queue/ContentCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs } from "@/components/ui/tabs";
import {
  useContentList,
  useCopyContent,
  useDeleteContent,
  usePublishedContent,
  useScheduledContent,
  useUpdateContent,
} from "@/hooks/useContent";
import type { ContentItem } from "@/lib/types";

const TABS = [
  { key: "drafts", label: "Drafts" },
  { key: "scheduled", label: "Scheduled" },
  { key: "published", label: "Published" },
];
const VALID_TAB_KEYS = new Set(TABS.map((tab) => tab.key));

function resolveTab(value: string | null) {
  return value && VALID_TAB_KEYS.has(value) ? value : "drafts";
}

export default function QueuePage() {
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab");
  const [tab, setTab] = useState(() => resolveTab(tabParam));
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const next = resolveTab(tabParam);
    setTab((current) => (current === next ? current : next));
    setPage(1);
  }, [tabParam]);

  const drafts = useContentList({ page, limit: 20, search, status: tab === "drafts" ? undefined : undefined });
  const scheduled = useScheduledContent();
  const published = usePublishedContent(page);

  const copyMutation = useCopyContent();
  const deleteMutation = useDeleteContent();
  const updateMutation = useUpdateContent();

  const data = useMemo(() => {
    if (tab === "scheduled") return scheduled.data;
    if (tab === "published") return published.data;
    return drafts.data;
  }, [tab, drafts.data, scheduled.data, published.data]);

  const isLoading = drafts.isLoading || scheduled.isLoading || published.isLoading;

  const handleCopy = async (item: ContentItem) => {
    try {
      await navigator.clipboard.writeText(item.hebrew_draft || item.original_text);
      await copyMutation.mutateAsync(item.id);
      toast.success("Copied");
    } catch {
      toast.error("Copy failed");
    }
  };

  const handleDelete = async (item: ContentItem) => {
    try {
      await deleteMutation.mutateAsync(item.id);
      toast.success("Deleted");
    } catch {
      toast.error("Delete failed");
    }
  };

  const handleReschedule = async (item: ContentItem) => {
    const next = window.prompt("Enter ISO datetime (YYYY-MM-DDTHH:mm)", item.scheduled_at?.slice(0, 16) || "");
    if (!next) {
      return;
    }
    try {
      await updateMutation.mutateAsync({
        id: item.id,
        payload: {
          scheduled_at: new Date(next).toISOString(),
          status: "approved",
        },
      });
      toast.success("Rescheduled");
    } catch {
      toast.error("Reschedule failed");
    }
  };

  return (
    <div className="space-y-5">
      <header className="surface-glow rounded-3xl px-5 py-5 md:px-6 md:py-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-display text-3xl leading-tight">Queue</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">Manage drafts, scheduling windows, and publication history.</p>
          </div>
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Search content"
            className="max-w-xs"
          />
        </div>
      </header>

      <Tabs
        tabs={TABS}
        active={tab}
        onChange={(next) => {
          setTab(next);
          setPage(1);
        }}
      />

      {isLoading ? (
        <p className="text-sm text-[var(--muted)]">Loading...</p>
      ) : (data?.items || []).length === 0 ? (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-4 py-5 text-sm text-[var(--muted)]">
          No items.
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {(data?.items || []).map((item) => (
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

      {data && data.total > page * data.per_page ? (
        <Button type="button" variant="secondary" onClick={() => setPage((current) => current + 1)}>
          Load more
        </Button>
      ) : null}
    </div>
  );
}
