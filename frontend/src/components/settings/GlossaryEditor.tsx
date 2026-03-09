"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useGlossary, useUpdateGlossary } from "@/hooks/useSettings";

interface Pair {
  en: string;
  he: string;
}

export function GlossaryEditor() {
  const glossaryQuery = useGlossary();
  const updateGlossary = useUpdateGlossary();
  const [draftRows, setDraftRows] = useState<Pair[] | null>(null);
  const baseRows = useMemo(() => {
    const terms = glossaryQuery.data || {};
    const entries = Object.entries(terms).map(([en, he]) => ({ en, he }));
    return entries.length ? entries : [{ en: "", he: "" }];
  }, [glossaryQuery.data]);
  const rows = draftRows ?? baseRows;

  const save = async () => {
    const payload: Record<string, string> = {};
    rows.forEach((row) => {
      if (row.en.trim() && row.he.trim()) {
        payload[row.en.trim()] = row.he.trim();
      }
    });

    try {
      await updateGlossary.mutateAsync(payload);
      setDraftRows(null);
      toast.success("Glossary saved");
    } catch {
      toast.error("Failed to save glossary");
    }
  };

  return (
    <div className="space-y-3">
      {rows.map((row, index) => (
        <div key={index} className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
          <Input
            value={row.en}
            onChange={(event) => {
              setDraftRows((prev) => {
                const current = prev ?? rows;
                const copy = [...current];
                copy[index] = { ...copy[index], en: event.target.value };
                return copy;
              });
            }}
            placeholder="English"
            dir="ltr"
          />
          <Input
            value={row.he}
            onChange={(event) => {
              setDraftRows((prev) => {
                const current = prev ?? rows;
                const copy = [...current];
                copy[index] = { ...copy[index], he: event.target.value };
                return copy;
              });
            }}
            placeholder="Hebrew"
            dir="rtl"
            lang="he"
          />
          <Button
            variant="ghost"
            onClick={() => setDraftRows((prev) => (prev ?? rows).filter((_, idx) => idx !== index))}
            disabled={rows.length === 1}
          >
            Delete
          </Button>
        </div>
      ))}

      <div className="flex gap-2">
        <Button variant="secondary" onClick={() => setDraftRows((prev) => [...(prev ?? rows), { en: "", he: "" }])}>
          Add Row
        </Button>
        <Button onClick={save} disabled={updateGlossary.isPending}>
          Save
        </Button>
      </div>
    </div>
  );
}
