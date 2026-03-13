"use client";

import { useQuery } from "@tanstack/react-query";

import api from "@/lib/api";

interface SessionHealth {
  status: "valid" | "warning" | "expired" | "missing";
  file_exists: boolean;
  age_hours: number | null;
  message: string;
}

export function useSessionStatus() {
  return useQuery<SessionHealth>({
    queryKey: ["scraper-session-health"],
    queryFn: async () => {
      const res = await api.get("/health/scraper-session");
      return res.data;
    },
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}
