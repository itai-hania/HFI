"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import api from "@/lib/api";

interface ContentFromThreadRequest {
  url: string;
  mode: "consolidated" | "separate";
  auto_translate: boolean;
  download_media: boolean;
}

interface SavedItem {
  id: number;
  status: string;
}

interface ContentFromThreadResponse {
  mode: string;
  thread_url: string;
  tweet_count: number;
  saved_items: SavedItem[];
}

export function useContentFromThread() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ContentFromThreadRequest) => {
      const { data } = await api.post<ContentFromThreadResponse>(
        "/api/content/from-thread",
        payload,
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content"] });
    },
  });
}
