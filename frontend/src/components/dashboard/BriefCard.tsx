import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BriefStory } from "@/lib/types";

export function BriefCard({ story, index, onTranslate }: { story: BriefStory; index: number; onTranslate: (story: BriefStory) => void }) {
  const router = useRouter();

  return (
    <Card className="lift-hover h-full">
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <Badge>Brief #{index + 1}</Badge>
          <Badge>{story.source_count} sources</Badge>
        </div>
        <CardTitle className="mt-2 text-xl leading-snug">{story.title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm leading-6 text-[var(--muted)]">{story.summary}</p>
        <div className="flex flex-wrap gap-2 text-xs text-[var(--muted)]">
          {story.sources.map((source) => (
            <span key={source} className="rounded-full border border-[var(--border)] bg-[rgba(255,255,255,0.02)] px-2 py-1">
              {source}
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <Button onClick={() => router.push(`/create?source=trend&id=${index + 1}&text=${encodeURIComponent(story.title)}`)}>
            Write
          </Button>
          <Button variant="secondary" onClick={() => onTranslate(story)}>
            Translate
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
