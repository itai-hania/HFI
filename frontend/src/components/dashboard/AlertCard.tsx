"use client";

import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { AlertItem } from "@/lib/types";

interface AlertCardProps {
  alert: AlertItem;
  onDismiss: (id: number) => void;
}

export function AlertCard({ alert, onDismiss }: AlertCardProps) {
  const router = useRouter();
  const content = alert.content;

  return (
    <Card className="border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/20">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <p className="font-semibold truncate">{content.title}</p>
            {content.summary && (
              <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{content.summary}</p>
            )}
            <div className="flex gap-2 mt-2">
              <Badge variant="outline" className="text-xs">📡 {content.source_count} sources</Badge>
            </div>
          </div>
          <div className="flex gap-1 shrink-0">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                const text = `${content.title}\n\n${content.summary || ""}`;
                router.push(`/create?text=${encodeURIComponent(text)}`);
              }}
            >
              Write
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onDismiss(alert.id)}>
              ✕
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
