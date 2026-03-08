"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { AngleSelector } from "@/components/create/AngleSelector";
import { HebrewEditor } from "@/components/create/HebrewEditor";
import { SourceInput } from "@/components/create/SourceInput";
import { VariantCards } from "@/components/create/VariantCards";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useCopyContent, useCreateContent, useUpdateContent } from "@/hooks/useContent";
import { useGenerate } from "@/hooks/useGenerate";
import { useTranslate } from "@/hooks/useTranslate";
import type { Variant } from "@/lib/types";

function looksLikeUrl(value: string) {
  return /^https?:\/\//i.test(value.trim());
}

export default function CreatePage() {
  const params = useSearchParams();
  const initialSource = params.get("text") || params.get("source") || "";
  const [sourceText, setSourceText] = useState(initialSource);
  const [angle, setAngle] = useState("news");
  const [variants, setVariants] = useState<Variant[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [editorText, setEditorText] = useState("");
  const [scheduleAt, setScheduleAt] = useState("");
  const [contentId, setContentId] = useState<number | null>(null);

  const generate = useGenerate();
  const translate = useTranslate();
  const createContent = useCreateContent();
  const updateContent = useUpdateContent();
  const copyContent = useCopyContent();

  async function handleGenerate() {
    if (!sourceText.trim()) {
      toast.error("Source is required");
      return;
    }

    try {
      const data = await generate.mutateAsync({
        source_text: sourceText,
        num_variants: 3,
        angles: [angle],
      });

      const nextVariants = data.variants.length
        ? data.variants
        : [
            {
              angle,
              label: "Generated",
              content: "No content generated",
              char_count: 0,
              is_valid_hebrew: false,
              quality_score: 0,
            },
          ];
      setVariants(nextVariants);
      setSelectedIndex(0);
      setEditorText(nextVariants[0]?.content || "");
      toast.success("Generated variants");
    } catch {
      toast.error("Generation failed");
    }
  }

  async function handleTranslateSource() {
    if (!sourceText.trim()) {
      toast.error("Source is required");
      return;
    }

    try {
      const translated = await translate.mutateAsync(
        looksLikeUrl(sourceText) ? { url: sourceText } : { text: sourceText },
      );
      setEditorText(translated.hebrew_text);
      toast.success("Translation ready");
    } catch {
      toast.error("Translation failed");
    }
  }

  async function persistDraft(status: "processed" | "approved") {
    const payload = {
      source_url: looksLikeUrl(sourceText)
        ? sourceText
        : `https://manual.local/content/${Date.now()}`,
      original_text: sourceText,
      hebrew_draft: editorText,
      content_type: "generation",
      status,
      scheduled_at: scheduleAt ? new Date(scheduleAt).toISOString() : null,
    };

    if (contentId) {
      await updateContent.mutateAsync({
        id: contentId,
        payload: {
          hebrew_draft: editorText,
          status,
          scheduled_at: payload.scheduled_at,
        },
      });
      return contentId;
    }

    const created = await createContent.mutateAsync(payload);
    setContentId(created.id);
    return created.id;
  }

  async function handleSaveDraft() {
    if (!editorText.trim()) {
      toast.error("Nothing to save");
      return;
    }

    try {
      await persistDraft("processed");
      toast.success("Draft saved");
    } catch {
      toast.error("Failed to save draft");
    }
  }

  async function handleSchedule() {
    if (!editorText.trim()) {
      toast.error("Nothing to schedule");
      return;
    }
    if (!scheduleAt) {
      toast.error("Pick a date and time");
      return;
    }

    try {
      await persistDraft("approved");
      toast.success("Scheduled");
    } catch {
      toast.error("Failed to schedule");
    }
  }

  async function handleCopy() {
    if (!editorText.trim()) {
      toast.error("Nothing to copy");
      return;
    }

    try {
      await navigator.clipboard.writeText(editorText);
      if (contentId) {
        await copyContent.mutateAsync(contentId);
      }
      toast.success("Copied");
    } catch {
      toast.error("Failed to copy");
    }
  }

  useEffect(() => {
    const handler = async (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        await handleGenerate();
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "c") {
        if ((document.activeElement as HTMLElement | null)?.tagName === "TEXTAREA") {
          return;
        }
        event.preventDefault();
        await handleCopy();
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  const busy =
    generate.isPending ||
    translate.isPending ||
    createContent.isPending ||
    updateContent.isPending ||
    copyContent.isPending;

  const handleSelectVariant = (index: number) => {
    setSelectedIndex(index);
    const variant = variants[index];
    if (variant) {
      setEditorText(variant.content);
    }
  };

  return (
    <div className="space-y-6">
      <header className="surface-glow rounded-3xl px-5 py-5 md:px-6 md:py-6">
        <h2 className="font-display text-3xl leading-tight">Create</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Source {"->"} Angle {"->"} Generate {"->"} Pick {"->"} Edit {"->"} Copy or Save
        </p>
        <div className="mt-4 flex flex-wrap gap-2 text-xs text-[var(--muted)]">
          <span className="rounded-full border border-[var(--border)] bg-[rgba(255,255,255,0.03)] px-2.5 py-1">Shortcut: Ctrl/Cmd + Enter</span>
          <span className="rounded-full border border-[var(--border)] bg-[rgba(255,255,255,0.03)] px-2.5 py-1">Target: up to 280 chars</span>
          <span className="rounded-full border border-[var(--border)] bg-[rgba(255,255,255,0.03)] px-2.5 py-1">Hebrew first</span>
        </div>
      </header>

      <Card className="lift-hover">
        <CardHeader>
          <CardTitle>Workflow</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <SourceInput value={sourceText} onChange={setSourceText} />
          <AngleSelector value={angle} onChange={setAngle} />
          <div className="flex flex-wrap gap-2">
            <Button onClick={handleGenerate} disabled={busy}>
              Generate (Ctrl+Enter)
            </Button>
            <Button variant="secondary" onClick={handleTranslateSource} disabled={busy}>
              Translate Source
            </Button>
          </div>
        </CardContent>
      </Card>

      <VariantCards variants={variants} selectedIndex={selectedIndex} onSelect={handleSelectVariant} />

      <Card className="lift-hover">
        <CardContent className="py-5">
          <HebrewEditor
            value={editorText}
            onChange={setEditorText}
            scheduleAt={scheduleAt}
            onScheduleAt={setScheduleAt}
            onCopy={handleCopy}
            onSaveDraft={handleSaveDraft}
            onSchedule={handleSchedule}
            disabled={busy}
          />
        </CardContent>
      </Card>
    </div>
  );
}
