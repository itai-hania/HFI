import { format } from "date-fns";

import { Badge } from "@/components/ui/badge";
import { textDir } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ContentItem } from "@/lib/types";

export function ScheduleTimeline({ items, loading }: { items: ContentItem[]; loading: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Today&apos;s Schedule</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : items.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No scheduled posts yet.</p>
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <div
                key={item.id}
                className="relative rounded-2xl border border-[var(--border)] bg-[var(--card-hover)] px-4 py-3 before:absolute before:left-0 before:top-0 before:h-full before:w-1 before:rounded-l-2xl before:bg-[linear-gradient(180deg,var(--accent-soft),var(--accent))] before:content-['']"
              >
                <div className="flex items-center justify-between gap-3">
                  <Badge>{item.scheduled_at ? format(new Date(item.scheduled_at), "HH:mm") : "Unscheduled"}</Badge>
                  <span className="text-xs text-[var(--muted)]">#{item.id}</span>
                </div>
                <p className="mt-2 line-clamp-2 text-sm" dir={textDir(item.hebrew_draft || item.original_text)}>
                  {item.hebrew_draft || item.original_text}
                </p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
