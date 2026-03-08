"use client";

import { useMutation } from "@tanstack/react-query";

import api from "@/lib/api";

interface TranslatePayload {
  text?: string;
  url?: string;
}

export function useTranslate() {
  return useMutation({
    mutationFn: async (payload: TranslatePayload) => {
      const { data } = await api.post<{ hebrew_text: string; original_text: string; source_type?: string }>(
        "/api/generation/translate",
        payload,
      );
      return data;
    },
  });
}
