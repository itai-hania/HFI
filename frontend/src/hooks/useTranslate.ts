"use client";

import { useMutation } from "@tanstack/react-query";

import api from "@/lib/api";

interface TranslatePayload {
  text?: string;
  url?: string;
}

interface TranslateResponse {
  hebrew_text: string;
  original_text: string;
  source_type?: string;
  title?: string;
  canonical_url?: string;
  source_domain?: string;
  preview_text?: string;
}

export function useTranslate() {
  return useMutation({
    mutationFn: async (payload: TranslatePayload) => {
      const { data } = await api.post<TranslateResponse>("/api/generation/translate", payload);
      return data;
    },
  });
}
