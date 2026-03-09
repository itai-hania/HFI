"use client";

import { useQuery } from "@tanstack/react-query";

import api from "@/lib/api";
import type { ContentListResponse } from "@/lib/types";

export function useLibrary(params: {
  search?: string;
  status?: string;
  page?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["library", params],
    queryFn: async () => {
      const { data } = await api.get<ContentListResponse>("/api/content/drafts", {
        params: {
          search: params.search || undefined,
          status: params.status || undefined,
          page: params.page || 1,
          limit: params.limit || 30,
        },
      });
      return data;
    },
  });
}
