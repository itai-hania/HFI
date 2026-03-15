"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface FeedbackWeightsData {
  excluded_keywords: string[];
  keyword_counts: Record<string, number>;
}

export function FeedbackWeights() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["feedback-weights"],
    queryFn: async () => {
      const { data } = await api.get<FeedbackWeightsData>("/api/notifications/brief/feedback/weights");
      return data;
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => api.delete("/api/notifications/brief/feedback"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feedback-weights"] });
      toast.success("Feedback reset");
    },
  });

  if (isLoading) return <p className="text-sm text-[var(--muted)]">Loading...</p>;

  const counts = data?.keyword_counts || {};
  const sorted = Object.entries(counts).sort(([, a], [, b]) => b - a);

  return (
    <div className="space-y-3">
      {sorted.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">No feedback yet. Use the thumbs-down button on brief stories to train your preferences.</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {sorted.map(([keyword, count]) => (
              <Badge
                key={keyword}
                className={count >= 3 ? "bg-red-900/40 text-red-300" : "bg-zinc-800 text-zinc-300"}
              >
                {keyword} ({count}){count >= 3 ? " — excluded" : ""}
              </Badge>
            ))}
          </div>
          <p className="text-xs text-[var(--muted)]">Keywords with 3+ downvotes are excluded from future briefs.</p>
          <Button variant="secondary" className="h-9 px-3 text-xs" onClick={() => {
            if (window.confirm("Reset all feedback? This will remove all learned keyword preferences.")) {
              resetMutation.mutate();
            }
          }} disabled={resetMutation.isPending}>
            {resetMutation.isPending ? "Resetting..." : "Reset All Feedback"}
          </Button>
        </>
      )}
    </div>
  );
}
