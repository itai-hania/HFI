"use client";

import { useState, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/lib/api";
import type { BriefStory } from "@/lib/types";

interface DraftState {
  storyIndex: number;
  hebrewText: string;
  isGenerating: boolean;
  isSaving: boolean;
}

export function useInlineDraft() {
  const [activeDraft, setActiveDraft] = useState<DraftState | null>(null);

  const generateMutation = useMutation({
    mutationFn: async (story: BriefStory) => {
      const sourceText = `${story.title}\n\n${story.summary || ""}`;
      const { data } = await api.post("/api/generation/post", {
        source_text: sourceText,
        num_variants: 1,
      });
      return data.variants?.[0]?.content || "";
    },
  });

  const saveMutation = useMutation({
    mutationFn: async ({ hebrewText, story, status }: { hebrewText: string; story: BriefStory; status: string }) => {
      const sourceUrl = story.source_urls?.[0] || `brief://${Date.now()}`;
      const sourceText = `${story.title}\n\n${story.summary || ""}`;
      const { data } = await api.post("/api/content", {
        source_url: sourceUrl,
        original_text: sourceText,
        hebrew_draft: hebrewText,
        content_type: "generation",
        status,
        generation_metadata: { origin: "brief_inline" },
      });
      return data;
    },
  });

  const openDraft = useCallback(async (story: BriefStory, index: number) => {
    setActiveDraft({ storyIndex: index, hebrewText: "", isGenerating: true, isSaving: false });
    try {
      const content = await generateMutation.mutateAsync(story);
      setActiveDraft((prev) => prev ? { ...prev, hebrewText: content, isGenerating: false } : null);
    } catch {
      toast.error("Failed to generate draft");
      setActiveDraft(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateText = useCallback((text: string) => {
    setActiveDraft((prev) => prev ? { ...prev, hebrewText: text } : null);
  }, []);

  const saveDraft = useCallback(async (story: BriefStory, status: "processed" | "approved") => {
    if (!activeDraft) return;
    setActiveDraft((prev) => prev ? { ...prev, isSaving: true } : null);
    try {
      await saveMutation.mutateAsync({ hebrewText: activeDraft.hebrewText, story, status });
      toast.success(status === "approved" ? "Added to queue" : "Draft saved");
      setActiveDraft(null);
    } catch {
      toast.error("Failed to save");
      setActiveDraft((prev) => prev ? { ...prev, isSaving: false } : null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeDraft]);

  const closeDraft = useCallback(() => {
    setActiveDraft(null);
  }, []);

  return { activeDraft, openDraft, updateText, saveDraft, closeDraft };
}
