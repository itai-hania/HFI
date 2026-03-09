"use client";

import Link from "next/link";
import { toast } from "sonner";

import { BriefCard } from "@/components/dashboard/BriefCard";
import { ScheduleTimeline } from "@/components/dashboard/ScheduleTimeline";
import { StatsBar } from "@/components/dashboard/StatsBar";
import { Button } from "@/components/ui/button";
import { useBrief } from "@/hooks/useBrief";
import { useScheduledContent } from "@/hooks/useContent";
import { useStats } from "@/hooks/useStats";
import { useTranslate } from "@/hooks/useTranslate";
import type { BriefStory } from "@/lib/types";

export default function DashboardPage() {
  const statsQuery = useStats();
  const briefQuery = useBrief();
  const scheduledQuery = useScheduledContent();
  const translate = useTranslate();

  const handleTranslate = async (story: BriefStory) => {
    try {
      const translated = await translate.mutateAsync({ text: story.title });
      toast.success("Translated", { description: translated.hebrew_text.slice(0, 120) });
    } catch {
      toast.error("Translation failed");
    }
  };

  return (
    <div className="space-y-6 md:space-y-7">
      <header className="surface-glow rounded-3xl px-5 py-5 md:px-6 md:py-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-[var(--muted)]">Mission Control</p>
            <h2 className="font-display mt-2 text-3xl leading-tight">Daily Content Ops</h2>
            <p className="mt-2 max-w-2xl text-sm text-[var(--muted)]">
              Prioritize today&apos;s opportunities, convert insights into high-quality Hebrew copy, and keep schedule coverage stable.
            </p>
          </div>
          <Link href="/create">
            <Button>Create From Brief</Button>
          </Link>
        </div>
      </header>

      <StatsBar
        loading={statsQuery.isLoading}
        stats={
          statsQuery.data || {
            drafts: 0,
            scheduledToday: 0,
            publishedToday: 0,
            total: 0,
          }
        }
      />

      <section className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <div className="space-y-3">
          <h3 className="font-display text-lg md:text-xl">Today&apos;s Brief</h3>
          {briefQuery.isLoading ? (
            <div className="text-sm text-[var(--muted)]">Loading brief...</div>
          ) : briefQuery.isError ? (
            <div className="rounded-2xl border border-[#7f1d1d] bg-[#2a1010] p-4 text-sm text-[#fecaca]">
              API unreachable. Please check backend connectivity.
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {(briefQuery.data?.stories || []).map((story, index) => (
                <BriefCard key={`${story.title}-${index}`} story={story} index={index} onTranslate={handleTranslate} />
              ))}
            </div>
          )}
        </div>

        <ScheduleTimeline items={scheduledQuery.data?.items || []} loading={scheduledQuery.isLoading} />
      </section>
    </div>
  );
}
