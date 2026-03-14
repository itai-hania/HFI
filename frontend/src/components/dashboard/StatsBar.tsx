import Link from "next/link";
import { BarChart3, Clock3, FileText, Send } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const ICONS = [FileText, Clock3, Send, BarChart3];
const ACCENTS = ["#1d9bf0", "#8b5cf6", "#22d3ee", "#34d399"];
const LINKS = ["/queue?tab=drafts", "/queue?tab=scheduled", "/queue?tab=published", "/library"];

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

  return (
    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item, index) => {
        const Icon = ICONS[index];
        return (
          <Link
            key={item.label}
            href={LINKS[index]}
            className="block h-full rounded-3xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            aria-label={`View ${item.value} ${item.label.toLowerCase()}`}
          >
            <Card className="lift-hover cursor-pointer overflow-hidden h-full relative">
              <CardContent className="py-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-medium text-[var(--muted)]">{item.label}</p>
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
              </CardContent>
              <div
                className="absolute bottom-0 left-0 h-0.5 w-full"
                style={{ backgroundColor: ACCENTS[index] }}
              />
            </Card>
          </Link>
        );
      })}
    </section>
  );
}
