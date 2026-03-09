"use client";

import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

function getSourceKind(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return "empty";
  }
  if (/^https?:\/\//i.test(trimmed)) {
    if (/x\.com|twitter\.com/i.test(trimmed)) {
      return "tweet";
    }
    return "article";
  }
  return "text";
}

export function SourceInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const kind = useMemo(() => getSourceKind(value), [value]);

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-display text-lg">Source</h3>
        {kind !== "empty" ? (
          <Badge>
            {kind === "tweet" ? "Tweet URL" : kind === "article" ? "Article URL" : `${value.length} chars`}
          </Badge>
        ) : null}
      </div>
      <p className="text-xs text-[var(--muted)]">Paste an article URL, an X post URL, or raw text to translate and refine.</p>

      {kind === "tweet" || kind === "article" ? (
        <Input value={value} onChange={(event) => onChange(event.target.value)} dir="ltr" placeholder="Paste URL" />
      ) : (
        <Textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Paste tweet/article text, or URL"
          className="min-h-[140px]"
          dir="auto"
        />
      )}
    </div>
  );
}
