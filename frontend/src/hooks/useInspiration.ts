"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "@/lib/api";
import type { InspirationAccount, InspirationSearchResponse } from "@/lib/types";

export function useInspirationAccounts() {
  return useQuery({
    queryKey: ["inspiration", "accounts"],
    queryFn: async () => {
      const { data } = await api.get<{ accounts: InspirationAccount[] }>("/api/inspiration/accounts");
      return data.accounts;
    },
  });
}

export function useAddInspirationAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { username: string; display_name?: string; category?: string }) => {
      const { data } = await api.post<InspirationAccount>("/api/inspiration/accounts", payload);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inspiration", "accounts"] }),
  });
}

export function useDeleteInspirationAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/api/inspiration/accounts/${id}`);
      return id;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inspiration", "accounts"] }),
  });
}

export function useSearchInspiration() {
  return useMutation({
    mutationFn: async (payload: {
      username: string;
      min_likes: number;
      keyword?: string;
      limit?: number;
      since?: string;
      until?: string;
    }) => {
      const { data } = await api.post<InspirationSearchResponse>("/api/inspiration/search", payload);
      return data;
    },
  });
}
