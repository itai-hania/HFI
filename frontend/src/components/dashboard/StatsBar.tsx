import { BarChart3, Clock3, FileText, Send } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const ICONS = [FileText, Clock3, Send, BarChart3];
const ACCENTS = ["#ec4899", "#8b5cf6", "#22d3ee", "#34d399"];

export function StatsBar({
  stats,
  loading,
}: {
  stats: { drafts: number; scheduledToday: number; publishedToday: number; total: number };
  loading: boolean;
}) {
  const items = [
    { label: "Drafts", value: stats.drafts },
    { label: "Scheduled Today", value: stats.scheduledToday },
    { label: "Published Today", value: stats.publishedToday },
    { label: "Total", value: stats.total },
  ];
  const maxValue = Math.max(...items.map((item) => item.value), 1);

  return (
    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item, index) => {
        const Icon = ICONS[index];
        const progress = Math.min(100, Math.round((item.value / maxValue) * 100));
        return (
          <Card key={item.label} className="lift-hover overflow-hidden">
            <CardContent className="space-y-4 py-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wider text-[var(--muted)]">{item.label}</p>
                  {loading ? (
                    <Skeleton className="mt-2 h-7 w-14" />
                  ) : (
                    <p className="mt-2 text-3xl font-semibold leading-none">{item.value}</p>
                  )}
                </div>
                <div
                  className="rounded-xl border p-2.5 text-[var(--muted)]"
                  style={{
                    borderColor: `${ACCENTS[index]}66`,
                    backgroundColor: `${ACCENTS[index]}1a`,
                    color: ACCENTS[index],
                  }}
                >
                  <Icon size={18} />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="h-1.5 overflow-hidden rounded-full bg-[rgba(255,255,255,0.08)]">
                  <div
                    className="h-full rounded-full transition-[width] duration-300"
                    style={{ width: `${loading ? 30 : progress}%`, backgroundColor: ACCENTS[index] }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </section>
  );
}
