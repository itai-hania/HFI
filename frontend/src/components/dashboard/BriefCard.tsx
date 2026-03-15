"use client";

import { useState } from "react";
import { ChevronDown, ExternalLink, Globe, Loader2, ThumbsDown } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BriefStory } from "@/lib/types";
import { cn } from "@/lib/utils";

const ISRAEL_SOURCES = ["Investing.com", "Google News Israel"];

function safeHref(value: string | null | undefined) {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

function formatRelativeAge(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  const diffMs = Date.now() - parsed.getTime();
  if (diffMs < 0) return "just now";
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function relevanceColor(score: number): string {
  if (score >= 70) return "bg-green-900/40 text-green-300";
  if (score >= 40) return "bg-amber-900/40 text-amber-300";
  return "bg-red-900/40 text-red-300";
}

function hasIsraelSource(sources: string[]): boolean {
  return sources.some((s) => ISRAEL_SOURCES.includes(s));
}

export function BriefCard({
  story,
  index,
  onTranslate,
  onWrite,
  onSkip,
  draftPanel,
}: {
  story: BriefStory;
  index: number;
  onTranslate: (story: BriefStory) => void | Promise<void>;
  onWrite: (story: BriefStory, index: number) => void;
  onSkip: (story: BriefStory, index: number) => void;
  draftPanel?: React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(true);
  const [translating, setTranslating] = useState(false);
  const toggleExpanded = () => setExpanded((prev) => !prev);
  const ageLabel = formatRelativeAge(story.published_at);
  const isIsrael = hasIsraelSource(story.sources || []);

  return (
    <Card className="lift-hover h-full">
      <CardHeader
        className="cursor-pointer select-none hover:bg-[rgba(255,255,255,0.04)] transition-colors duration-200 motion-reduce:transition-none rounded-t-3xl"
        onClick={toggleExpanded}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleExpanded();
          }
        }}
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        aria-label={`${expanded ? "Collapse" : "Expand"} brief #${index + 1}: ${story.title}`}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <Badge>Brief #{index + 1}</Badge>
            {isIsrael && <Badge className="text-xs"><Globe size={12} className="text-sky-400" /> Israel</Badge>}
          </div>
          <div className="flex items-center gap-1.5">
            {typeof story.relevance_score === "number" && (
              <Badge className={cn("text-xs", relevanceColor(story.relevance_score))}>
                ★{story.relevance_score}
              </Badge>
            )}
            <Badge>{story.source_count} sources</Badge>
            <ChevronDown
              size={16}
              className={cn(
                "text-[var(--muted)] transition-transform duration-200 motion-reduce:transition-none",
                expanded && "rotate-180"
              )}
            />
          </div>
        </div>
        <CardTitle className="mt-2 text-xl leading-snug">{story.title}</CardTitle>
        {ageLabel && (
          <p className="mt-1 text-xs text-[var(--muted)]">{ageLabel}</p>
        )}
      </CardHeader>

      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-200 motion-reduce:transition-none",
          expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        )}
      >
        <div className="overflow-hidden">
          {expanded ? (
            <CardContent className="space-y-4 pt-0">
              <p className="text-sm leading-6 text-[var(--muted)]">{story.summary}</p>

              {story.source_urls && story.source_urls.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs font-medium text-[var(--muted)]">Sources</p>
                  <div className="flex flex-col gap-1">
                    {story.source_urls.map((url, i) => {
                      const href = safeHref(url);
                      const domain = story.sources[i] || (href ? new URL(href).hostname : "Source");
                      if (!href) return null;
                      return (
                        <a
                          key={`${url}-${i}`}
                          href={href}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1.5 text-sm text-[var(--muted)] hover:text-[var(--ink)] hover:underline transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] rounded-sm w-fit"
                        >
                          <ExternalLink size={13} />
                          {domain}
                        </a>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="flex gap-2">
                <Button
                  onClick={(e) => {
                    e.stopPropagation();
                    onWrite(story, index);
                  }}
                >
                  Write
                </Button>
                <Button
                  variant="secondary"
                  disabled={translating}
                  onClick={async (e) => {
                    e.stopPropagation();
                    setTranslating(true);
                    try {
                      await onTranslate(story);
                    } finally {
                      setTranslating(false);
                    }
                  }}
                >
                  {translating ? <><Loader2 size={14} className="animate-spin" /> Translating...</> : "Translate"}
                </Button>
                <Button
                  variant="ghost"
                  className="h-11 w-11 p-0 text-[var(--muted)] hover:text-red-400"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSkip(story, index);
                  }}
                  aria-label={`Mark "${story.title}" as not relevant`}
                >
                  <ThumbsDown size={16} />
                </Button>
              </div>
              {draftPanel}
            </CardContent>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
