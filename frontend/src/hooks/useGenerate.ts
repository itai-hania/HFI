"use client";

import { useMutation } from "@tanstack/react-query";

import api from "@/lib/api";
import type { GeneratePostResponse } from "@/lib/types";

interface GeneratePayload {
  source_text: string;
  num_variants?: number;
  angles?: string[];
}

export function useGenerate() {
  return useMutation({
    mutationFn: async (payload: GeneratePayload) => {
      const { data } = await api.post<GeneratePostResponse>("/api/generation/post", payload);
      return data;
    },
  });
}
