"use client";

import Link from "next/link";
import { format } from "date-fns";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { ContentItem } from "@/lib/types";

function safeHref(value: string) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

function badgeStyle(status: string) {
  if (status === "approved") return "border-emerald-500/40 text-emerald-300";
  if (status === "published") return "border-cyan-500/40 text-cyan-300";
  if (status === "failed") return "border-red-500/40 text-red-300";
  if (status === "processed") return "border-amber-500/40 text-amber-300";
  return "";
}

export function ContentCard({
  item,
  onCopy,
  onDelete,
  onReschedule,
}: {
  item: ContentItem;
  onCopy: (item: ContentItem) => void;
  onDelete: (item: ContentItem) => void;
  onReschedule: (item: ContentItem) => void;
}) {
  const href = safeHref(item.source_url);

  return (
    <Card className="lift-hover">
      <CardContent className="space-y-3 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge className={badgeStyle(item.status)}>{item.status}</Badge>
          <Badge>{item.content_type}</Badge>
          {item.scheduled_at ? <Badge>{format(new Date(item.scheduled_at), "dd/MM HH:mm")}</Badge> : null}
        </div>

        <p className="text-right leading-7" dir="rtl">
          {item.hebrew_draft || item.original_text}
        </p>

        {href ? (
          <a href={href} target="_blank" rel="noreferrer" className="block truncate text-xs text-cyan-300 hover:underline" dir="ltr">
            {item.source_url}
          </a>
        ) : (
          <span className="block truncate text-xs text-[var(--muted)]" dir="ltr">
            {item.source_url}
          </span>
        )}

        <div className="flex flex-wrap gap-2">
          <Link href={`/create?edit=${item.id}`}>
            <Button variant="secondary">Edit</Button>
          </Link>
          <Button variant="secondary" onClick={() => onCopy(item)}>
            Copy
          </Button>
          <Button variant="secondary" onClick={() => onReschedule(item)}>
            Reschedule
          </Button>
          <Button variant="danger" onClick={() => onDelete(item)}>
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
