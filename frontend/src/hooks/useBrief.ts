"use client";

import { useQuery } from "@tanstack/react-query";

import api from "@/lib/api";
import type { BriefResponse } from "@/lib/types";

export function useBrief() {
  return useQuery({
    queryKey: ["brief"],
    queryFn: async () => {
      const { data } = await api.post<BriefResponse>("/api/notifications/brief");
      return data;
    },
  });
}
