"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "@/lib/api";
import type { ContentItem, ContentListResponse } from "@/lib/types";

interface ListParams {
  status?: string;
  search?: string;
  page?: number;
  limit?: number;
}

export function useContentList(params: ListParams) {
  return useQuery({
    queryKey: ["content", params],
    queryFn: async () => {
      const { data } = await api.get<ContentListResponse>("/api/content/drafts", { params });
      return data;
    },
  });
}

export function useScheduledContent() {
  return useQuery({
    queryKey: ["content", "scheduled"],
    queryFn: async () => {
      const { data } = await api.get<ContentListResponse>("/api/content/scheduled", { params: { page: 1, limit: 100 } });
      return data;
    },
  });
}

export function usePublishedContent(page = 1) {
  return useQuery({
    queryKey: ["content", "published", page],
    queryFn: async () => {
      const { data } = await api.get<ContentListResponse>("/api/content/published", { params: { page, limit: 20 } });
      return data;
    },
  });
}

export function useCreateContent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<ContentItem> & { source_url: string; original_text: string }) => {
      const { data } = await api.post<ContentItem>("/api/content", payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content"] });
    },
  });
}

export function useUpdateContent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<ContentItem> }) => {
      const { data } = await api.patch<ContentItem>(`/api/content/${id}`, payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content"] });
    },
  });
}

export function useDeleteContent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/api/content/${id}`);
      return id;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content"] });
    },
  });
}

export function useCopyContent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.post<ContentItem>(`/api/content/${id}/copy`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content"] });
    },
  });
}
