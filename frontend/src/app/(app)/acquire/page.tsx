"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, ExternalLink, Loader2, XIcon } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useContentFromThread } from "@/hooks/useAcquire";
import { useContentItem } from "@/hooks/useContent";
import { textDir } from "@/lib/utils";

const X_URL_REGEX = /^https?:\/\/(x\.com|twitter\.com)\/\w+\/status\/\d+/i;

function isValidXUrl(url: string): boolean {
  return X_URL_REGEX.test(url.trim());
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    processed: "border-emerald-700 bg-emerald-950 text-emerald-300",
    pending: "border-amber-700 bg-amber-950 text-amber-300",
    failed: "border-red-700 bg-red-950 text-red-300",
  };
  return (
    <Badge className={styles[status] || ""}>
      {status}
    </Badge>
  );
}

function ResultItem({ itemId }: { itemId: number }) {
  const query = useContentItem(itemId);
  const item = query.data;

  if (query.isLoading) {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 p-4 text-sm text-[var(--muted)]">
        Loading content #{itemId}...
      </div>
    );
  }

  if (!item) return null;

  return (
    <div className="space-y-3 rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-[var(--muted)]">#{item.id}</span>
        <StatusBadge status={item.status} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-[var(--muted)]">
            English (Source)
          </p>
          <div
            dir="ltr"
            className="whitespace-pre-wrap rounded-xl border border-[var(--border)] bg-[rgba(255,255,255,0.02)] p-3 text-sm leading-relaxed text-[var(--ink)]"
          >
            {item.original_text || "—"}
          </div>
        </div>

        <div className="space-y-1.5">
          <p className="text-xs font-medium text-[var(--muted)]">
            Hebrew (Draft)
          </p>
          <div
            dir={textDir(item.hebrew_draft)}
            className="whitespace-pre-wrap rounded-xl border border-[var(--border)] bg-[rgba(255,255,255,0.02)] p-3 text-sm leading-relaxed text-[var(--ink)]"
          >
            {item.hebrew_draft || "— (no translation)"}
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <Link href={`/create?edit=${item.id}`}>
          <Button variant="secondary" className="text-xs">
            <ExternalLink size={14} />
            Edit in Studio
          </Button>
        </Link>
      </div>
    </div>
  );
}

export default function AcquirePage() {
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"consolidated" | "separate">("consolidated");
  const [autoTranslate, setAutoTranslate] = useState(true);
  const [downloadMedia, setDownloadMedia] = useState(false);

  const scrape = useContentFromThread();

  const trimmedUrl = url.trim();
  const validUrl = isValidXUrl(trimmedUrl);

  async function handleScrape() {
    if (!validUrl) {
      toast.error("Enter a valid X thread URL");
      return;
    }

    try {
      const result = await scrape.mutateAsync({
        url: trimmedUrl,
        mode,
        auto_translate: autoTranslate,
        download_media: downloadMedia,
      });
      toast.success(
        `Scraped ${result.tweet_count} tweet${result.tweet_count === 1 ? "" : "s"} → ${result.saved_items.length} item${result.saved_items.length === 1 ? "" : "s"} saved`,
      );
    } catch {
      toast.error("Scrape failed — check the URL and try again");
    }
  }

  const busy = scrape.isPending;

  return (
    <div className="space-y-6">
      <header className="surface-glow rounded-3xl px-5 py-5 md:px-6 md:py-6">
        <h2 className="font-display text-3xl leading-tight">Acquire</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Paste an X thread URL → scrape → translate → send to studio.
        </p>
      </header>

      <Card className="lift-hover">
        <CardHeader>
          <CardTitle>Scrape X Thread</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* URL input */}
          <div className="space-y-1.5">
            <label htmlFor="thread-url" className="text-xs font-medium text-[var(--muted)]">
              Thread URL
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  id="thread-url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://x.com/user/status/123456789"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && validUrl && !busy) handleScrape();
                  }}
                />
                {trimmedUrl.length > 0 && (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2">
                    {validUrl ? <Check size={14} className="text-emerald-400" /> : <XIcon size={14} className="text-red-400" />}
                  </span>
                )}
              </div>
            </div>
            {trimmedUrl.length > 0 && !validUrl && (
              <p className="text-xs text-red-400">Enter a valid x.com or twitter.com status URL</p>
            )}
          </div>

          {/* Mode selector */}
          <fieldset className="space-y-2">
            <legend className="text-xs font-medium text-[var(--muted)]">
              Mode
            </legend>
            <div className="flex gap-3">
              {(["consolidated", "separate"] as const).map((m) => (
                <label
                  key={m}
                  className={`flex cursor-pointer items-center gap-2 rounded-xl border px-4 py-2.5 text-sm transition duration-200 ${
                    mode === m
                      ? "border-[var(--accent)]/40 bg-[linear-gradient(135deg,rgba(29,155,240,0.16),rgba(29,155,240,0.06))] text-[var(--accent-ink)]"
                      : "border-[var(--border)] bg-[var(--card)] text-[var(--muted)] hover:border-[var(--border)] hover:bg-[var(--card-hover)]"
                  }`}
                >
                  <input
                    type="radio"
                    name="mode"
                    value={m}
                    checked={mode === m}
                    onChange={() => setMode(m)}
                    className="sr-only"
                  />
                  <span className="capitalize">{m}</span>
                  <span className="text-xs text-[var(--muted)]">
                    {m === "consolidated" ? "(single post)" : "(per-tweet)"}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          {/* Options */}
          <fieldset className="space-y-2">
            <legend className="text-xs font-medium text-[var(--muted)]">
              Options
            </legend>
            <div className="flex flex-wrap gap-4">
              <label className="flex cursor-pointer items-center gap-2 text-sm text-[var(--ink)]">
                <input
                  type="checkbox"
                  checked={autoTranslate}
                  onChange={(e) => setAutoTranslate(e.target.checked)}
                  className="size-4 cursor-pointer rounded border-[var(--border)] accent-[var(--accent)]"
                />
                Auto-translate
              </label>
              <label className="flex cursor-pointer items-center gap-2 text-sm text-[var(--ink)]">
                <input
                  type="checkbox"
                  checked={downloadMedia}
                  onChange={(e) => setDownloadMedia(e.target.checked)}
                  className="size-4 cursor-pointer rounded border-[var(--border)] accent-[var(--accent)]"
                />
                Download media
              </label>
            </div>
          </fieldset>

          {/* Scrape button */}
          <Button onClick={handleScrape} disabled={!validUrl || busy}>
            {busy ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Scraping...
              </>
            ) : (
              "Scrape & Process"
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Error */}
      {scrape.isError && (
        <div className="rounded-2xl border border-[#7f1d1d] bg-[#2a1010] p-4 text-sm text-[#fecaca]" role="alert">
          Scrape failed. Check the URL is a valid X thread and try again.
          {scrape.error instanceof Error && scrape.error.message && (
            <p className="mt-1 text-xs text-red-400">{scrape.error.message}</p>
          )}
        </div>
      )}

      {/* Results */}
      {scrape.data && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Results</CardTitle>
              <div className="flex gap-2 text-xs text-[var(--muted)]">
                <Badge>{scrape.data.mode}</Badge>
                <Badge>{scrape.data.tweet_count} tweet{scrape.data.tweet_count === 1 ? "" : "s"}</Badge>
                <Badge>{scrape.data.saved_items.length} saved</Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {scrape.data.saved_items.map((item) => (
              <ResultItem key={item.id} itemId={item.id} />
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
