"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "@/lib/api";
import type { BriefResponse } from "@/lib/types";

export function useBrief() {
  return useQuery({
    queryKey: ["brief"],
    queryFn: async () => {
      const { data } = await api.get<BriefResponse>("/api/notifications/brief/latest");
      return data;
    },
    refetchInterval: 300_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useRefreshBrief() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<BriefResponse>("/api/notifications/brief", null, {
        params: { force_refresh: true },
      });
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["brief"], data);
    },
  });
}
