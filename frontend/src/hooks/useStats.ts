"use client";

import { useQuery } from "@tanstack/react-query";

import api from "@/lib/api";

interface Stats {
  drafts: number;
  scheduledToday: number;
  publishedToday: number;
  total: number;
}

function isToday(value: string | null | undefined) {
  if (!value) {
    return false;
  }
  const date = new Date(value);
  const now = new Date();
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}

export function useStats() {
  return useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: async (): Promise<Stats> => {
      const [drafts, scheduled, published, total] = await Promise.all([
        api.get("/api/content/drafts", { params: { status: "pending", page: 1, limit: 1 } }),
        api.get("/api/content/scheduled", { params: { page: 1, limit: 100 } }),
        api.get("/api/content/published", { params: { page: 1, limit: 100 } }),
        api.get("/api/content/drafts", { params: { page: 1, limit: 1 } }),
      ]);

      const scheduledItems = scheduled.data.items || [];
      const publishedItems = published.data.items || [];

      return {
        drafts: drafts.data.total || 0,
        scheduledToday: scheduledItems.filter((item: { scheduled_at?: string | null }) => isToday(item.scheduled_at || null)).length,
        publishedToday: publishedItems.filter((item: { created_at?: string | null }) => isToday(item.created_at || null)).length,
        total: total.data.total || 0,
      };
    },
  });
}
