"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "@/lib/api";
import type { StyleExample } from "@/lib/types";

export function useGlossary() {
  return useQuery({
    queryKey: ["settings", "glossary"],
    queryFn: async () => {
      const { data } = await api.get<{ terms: Record<string, string> }>("/api/settings/glossary");
      return data.terms;
    },
  });
}

export function useUpdateGlossary() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (terms: Record<string, string>) => {
      const { data } = await api.put<{ terms: Record<string, string> }>("/api/settings/glossary", { terms });
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "glossary"] }),
  });
}

export function usePreferences() {
  return useQuery({
    queryKey: ["settings", "preferences"],
    queryFn: async () => {
      const { data } = await api.get<{ preferences: Record<string, unknown> }>("/api/settings/preferences");
      return data.preferences;
    },
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (preferences: Record<string, unknown>) => {
      const { data } = await api.put<{ preferences: Record<string, unknown> }>(
        "/api/settings/preferences",
        { preferences },
      );
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "preferences"] }),
  });
}

export function useStyleExamples() {
  return useQuery({
    queryKey: ["settings", "style"],
    queryFn: async () => {
      const { data } = await api.get<{ items: StyleExample[] }>("/api/settings/style-examples");
      return data.items;
    },
  });
}

export function useAddStyleExample() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { content: string; topic_tags?: string[]; source_type?: string }) => {
      const { data } = await api.post<StyleExample>("/api/settings/style-examples", payload);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "style"] }),
  });
}
