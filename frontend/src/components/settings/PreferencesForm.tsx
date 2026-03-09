"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { usePreferences, useUpdatePreferences } from "@/hooks/useSettings";

export function PreferencesForm() {
  const preferencesQuery = usePreferences();
  const updatePreferences = useUpdatePreferences();

  const [draft, setDraft] = useState<{
    defaultAngle?: string;
    postsPerDay?: number;
    briefTimes?: string;
  }>({});

  const defaults = useMemo(() => {
    const prefs = preferencesQuery.data || {};
    return {
      defaultAngle: typeof prefs.default_angle === "string" ? prefs.default_angle : "news",
      postsPerDay: typeof prefs.posts_per_day === "number" ? prefs.posts_per_day : 4,
      briefTimes: Array.isArray(prefs.brief_times) ? prefs.brief_times.join(",") : "08:00,19:00",
    };
  }, [preferencesQuery.data]);

  const defaultAngle = draft.defaultAngle ?? defaults.defaultAngle;
  const postsPerDay = draft.postsPerDay ?? defaults.postsPerDay;
  const briefTimes = draft.briefTimes ?? defaults.briefTimes;

  const save = async () => {
    try {
      await updatePreferences.mutateAsync({
        default_angle: defaultAngle,
        posts_per_day: postsPerDay,
        brief_times: briefTimes
          .split(",")
          .map((time) => time.trim())
          .filter(Boolean),
      });
      setDraft({});
      toast.success("Preferences saved");
    } catch {
      toast.error("Failed to save preferences");
    }
  };

  return (
    <div className="grid gap-3 md:grid-cols-4">
      <Select
        value={defaultAngle}
        onChange={(event) => setDraft((prev) => ({ ...prev, defaultAngle: event.target.value }))}
      >
        <option value="news">news</option>
        <option value="educational">educational</option>
        <option value="opinion">opinion</option>
      </Select>
      <Input
        type="number"
        min={1}
        max={20}
        value={postsPerDay}
        onChange={(event) => setDraft((prev) => ({ ...prev, postsPerDay: Number(event.target.value || 1) }))}
      />
      <Input
        value={briefTimes}
        onChange={(event) => setDraft((prev) => ({ ...prev, briefTimes: event.target.value }))}
        placeholder="08:00,19:00"
        dir="ltr"
      />
      <Button onClick={save} disabled={updatePreferences.isPending}>
        Save
      </Button>
    </div>
  );
}
