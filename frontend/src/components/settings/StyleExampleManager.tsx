"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAddStyleExample, useStyleExamples } from "@/hooks/useSettings";

export function StyleExampleManager() {
  const examplesQuery = useStyleExamples();
  const addExample = useAddStyleExample();
  const [content, setContent] = useState("");
  const [tags, setTags] = useState("");

  const save = async () => {
    if (!content.trim()) {
      toast.error("Content required");
      return;
    }
    try {
      await addExample.mutateAsync({
        content,
        topic_tags: tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        source_type: "manual",
      });
      setContent("");
      setTags("");
      toast.success("Style example added");
    } catch {
      toast.error("Failed to add style example");
    }
  };

  return (
    <div className="space-y-3">
      <Textarea value={content} onChange={(event) => setContent(event.target.value)} placeholder="Hebrew style example" dir="rtl" />
      <Input
        placeholder="topic tags (comma separated)"
        value={tags}
        onChange={(event) => setTags(event.target.value)}
      />
      <Button onClick={save} disabled={addExample.isPending}>
        Add Example
      </Button>

      <div className="space-y-2">
        {(examplesQuery.data || []).map((example) => (
          <div key={example.id} className="rounded-xl border border-[var(--border)] px-3 py-2">
            <p className="line-clamp-3 text-sm" dir="rtl">
              {example.content}
            </p>
            <p className="mt-1 text-xs text-[var(--muted)]">{(example.topic_tags || []).join(", ") || "no tags"}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
