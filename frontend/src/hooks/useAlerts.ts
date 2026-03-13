"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "@/lib/api";
import type { AlertsResponse } from "@/lib/types";

export function useAlerts() {
  return useQuery({
    queryKey: ["alerts"],
    queryFn: async () => {
      const { data } = await api.get<AlertsResponse>("/api/notifications/alerts", {
        params: { delivered: false },
      });
      return data;
    },
    refetchInterval: 60_000,
  });
}

export function useDismissAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (alertId: number) => {
      await api.patch(`/api/notifications/${alertId}/delivered`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}
