"use client";

import type { BriefTheme, BriefStory } from "@/lib/types";
import { BriefCard } from "./BriefCard";

export function BriefThemeSection({
  theme,
  startIndex,
  onTranslate,
  onWrite,
  onSkip,
  draftPanel,
}: {
  theme: BriefTheme;
  startIndex: number;
  onTranslate: (story: BriefStory) => void | Promise<void>;
  onWrite: (story: BriefStory, index: number) => void;
  onSkip: (story: BriefStory, index: number) => void;
  draftPanel?: (story: BriefStory, index: number) => React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-xl">{theme.emoji}</span>
        <h4 className="font-display text-base font-semibold">{theme.name}</h4>
      </div>
      <p className="text-sm text-[var(--muted)] -mt-1">{theme.takeaway}</p>
      <div className="grid gap-3 md:grid-cols-2">
        {theme.stories.map((story, i) => (
          <BriefCard
            key={`${story.title}-${startIndex + i}`}
            story={story}
            index={startIndex + i}
            onTranslate={onTranslate}
            onWrite={onWrite}
            onSkip={onSkip}
            draftPanel={draftPanel?.(story, startIndex + i)}
          />
        ))}
      </div>
    </div>
  );
}
