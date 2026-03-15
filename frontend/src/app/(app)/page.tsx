"use client";

import Link from "next/link";
import { AlertTriangle, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { AlertCard } from "@/components/dashboard/AlertCard";
import { BriefCard } from "@/components/dashboard/BriefCard";
import { BriefThemeSection } from "@/components/dashboard/BriefThemeSection";
import { ScheduleTimeline } from "@/components/dashboard/ScheduleTimeline";
import { StatsBar } from "@/components/dashboard/StatsBar";
import { Button } from "@/components/ui/button";
import { useAlerts, useDismissAlert } from "@/hooks/useAlerts";
import { useBrief, useRefreshBrief } from "@/hooks/useBrief";
import { useInlineDraft } from "@/hooks/useInlineDraft";
import { useScheduledContent } from "@/hooks/useContent";
import { useStats } from "@/hooks/useStats";
import { useTranslate } from "@/hooks/useTranslate";
import api from "@/lib/api";
import type { BriefStory } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

export default function DashboardPage() {
  const statsQuery = useStats();
  const briefQuery = useBrief();
  const refreshBrief = useRefreshBrief();
  const scheduledQuery = useScheduledContent();
  const alertsQuery = useAlerts();
  const dismissAlert = useDismissAlert();
  const translate = useTranslate();
  const { activeDraft, openDraft, updateText, saveDraft, closeDraft } = useInlineDraft();

  const handleTranslate = async (story: BriefStory) => {
    try {
      const translated = await translate.mutateAsync({ text: story.title });
      toast.success("Translated", { description: translated.hebrew_text.slice(0, 120) });
    } catch {
      toast.error("Translation failed");
    }
  };

  const handleWrite = (story: BriefStory, index: number) => {
    openDraft(story, index);
  };

  const handleSkip = async (story: BriefStory, _index: number) => {
    try {
      const keywords = story.title.toLowerCase().split(/\s+/).filter(w => w.length > 2);
      await api.post("/api/notifications/brief/feedback", {
        story_title: story.title,
        feedback_type: "not_relevant",
        keywords,
        source: "dashboard",
      });
      toast.success("Noted", { description: "We'll show less stories like this" });
    } catch {
      toast.error("Failed to submit feedback");
    }
  };

  const buildDraftPanel = (story: BriefStory, index: number): React.ReactNode => {
    if (!activeDraft || activeDraft.storyIndex !== index) return undefined;
    return (
      <div className="mt-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3">
        <label htmlFor={`draft-${index}`} className="text-xs font-medium text-[var(--muted)]">Hebrew Draft</label>
        {activeDraft.isGenerating ? (
          <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
            <Loader2 size={14} className="animate-spin" /> Generating...
          </div>
        ) : (
          <>
            <textarea
              id={`draft-${index}`}
              className="w-full min-h-[100px] rounded-xl border border-[var(--border)] bg-[var(--background)] p-3 text-sm leading-6 resize-y focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              dir="rtl"
              value={activeDraft.hebrewText}
              onChange={(e) => updateText(e.target.value)}
            />
            <div className="flex gap-2">
              <Button
                className="h-9 px-3 text-xs"
                variant="secondary"
                disabled={activeDraft.isSaving}
                onClick={() => saveDraft(story, "processed")}
              >
                Save Draft
              </Button>
              <Button
                className="h-9 px-3 text-xs"
                disabled={activeDraft.isSaving}
                onClick={() => saveDraft(story, "approved")}
              >
                Queue
              </Button>
              <Button className="h-9 px-3 text-xs" variant="ghost" onClick={closeDraft}>
                Close
              </Button>
            </div>
          </>
        )}
      </div>
    );
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

      {alertsQuery.data?.alerts && alertsQuery.data.alerts.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-display text-lg md:text-xl"><AlertTriangle size={16} className="inline text-red-400" /> Alerts ({alertsQuery.data.alerts.length})</h3>
          <div className="space-y-2">
            {alertsQuery.data.alerts.map((alert) => (
              <AlertCard key={alert.id} alert={alert} onDismiss={(id) => dismissAlert.mutate(id)} />
            ))}
          </div>
        </div>
      )}

      <section className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-lg md:text-xl">Today&apos;s Brief</h3>
            <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
              {briefQuery.dataUpdatedAt ? (
                <span>Updated {formatRelativeTime(briefQuery.dataUpdatedAt)}</span>
              ) : null}
              <Button
                variant="secondary"
                className="h-8 px-3 text-xs"
                onClick={() => refreshBrief.mutate()}
                disabled={refreshBrief.isPending}
              >
                {refreshBrief.isPending ? "Refreshing..." : "↻ Refresh"}
              </Button>
            </div>
          </div>
          {briefQuery.isLoading ? (
            <div className="text-sm text-[var(--muted)]">Loading brief...</div>
          ) : briefQuery.isError ? (
            <div className="rounded-2xl border border-red-900/50 bg-red-950/40 p-4 text-sm text-red-200">
              API unreachable. Please check backend connectivity.
            </div>
          ) : briefQuery.data?.themes && briefQuery.data.themes.length > 0 ? (
            <div className="space-y-6">
              {(() => {
                let runningIndex = 0;
                return briefQuery.data.themes.map((theme, themeIdx) => {
                  const section = (
                    <BriefThemeSection
                      key={theme.name + themeIdx}
                      theme={theme}
                      startIndex={runningIndex}
                      onTranslate={handleTranslate}
                      onWrite={handleWrite}
                      onSkip={handleSkip}
                      draftPanel={buildDraftPanel}
                    />
                  );
                  runningIndex += theme.stories.length;
                  return section;
                });
              })()}
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {(briefQuery.data?.stories || []).map((story, index) => (
                <BriefCard
                  key={`${story.title}-${index}`}
                  story={story}
                  index={index}
                  onTranslate={handleTranslate}
                  onWrite={handleWrite}
                  onSkip={handleSkip}
                  draftPanel={buildDraftPanel(story, index)}
                />
              ))}
            </div>
          )}
        </div>

        <ScheduleTimeline items={scheduledQuery.data?.items || []} loading={scheduledQuery.isLoading} />
      </section>
    </div>
  );
}
