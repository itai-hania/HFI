"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BriefStory } from "@/lib/types";
import { cn } from "@/lib/utils";

function safeHref(value: string | null | undefined) {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

export function BriefCard({
  story,
  index,
  onTranslate,
}: {
  story: BriefStory;
  index: number;
  onTranslate: (story: BriefStory) => void;
}) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const toggleExpanded = () => setExpanded((prev) => !prev);

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
          <Badge>Brief #{index + 1}</Badge>
          <div className="flex items-center gap-2">
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
                  <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">Sources</p>
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
                    router.push(`/create?source=trend&id=${index + 1}&text=${encodeURIComponent(story.title)}`);
                  }}
                >
                  Write
                </Button>
                <Button
                  variant="secondary"
                  onClick={(e) => {
                    e.stopPropagation();
                    onTranslate(story);
                  }}
                >
                  Translate
                </Button>
              </div>
            </CardContent>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
