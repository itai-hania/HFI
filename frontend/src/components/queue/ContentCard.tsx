"use client";

import { useState } from "react";
import Link from "next/link";
import { format } from "date-fns";
import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { ContentItem } from "@/lib/types";
import { textDir } from "@/lib/utils";

function safeHref(value: string) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

function badgeStyle(status: string) {
  if (status === "approved") return "border-emerald-500/40 text-emerald-300";
  if (status === "published") return "border-cyan-500/40 text-cyan-300";
  if (status === "failed") return "border-red-500/40 text-red-300";
  if (status === "processed") return "border-amber-500/40 text-amber-300";
  return "";
}

export function ContentCard({
  item,
  onCopy,
  onDelete,
  onReschedule,
}: {
  item: ContentItem;
  onCopy: (item: ContentItem) => void | Promise<void>;
  onDelete: (item: ContentItem) => void | Promise<void>;
  onReschedule: (item: ContentItem) => void | Promise<void>;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [copying, setCopying] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [rescheduling, setRescheduling] = useState(false);
  const href = safeHref(item.source_url);

  const handleCopy = async () => {
    setCopying(true);
    try { await onCopy(item); } finally { setCopying(false); }
  };

  const handleReschedule = async () => {
    setRescheduling(true);
    try { await onReschedule(item); } finally { setRescheduling(false); }
  };

  const handleConfirmDelete = async () => {
    setConfirmDelete(false);
    setDeleting(true);
    try { await onDelete(item); } finally { setDeleting(false); }
  };

  return (
    <Card className="lift-hover">
      <CardContent className="space-y-3 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge className={badgeStyle(item.status)}>{item.status}</Badge>
          <Badge>{item.content_type}</Badge>
          {item.scheduled_at ? <Badge>{format(new Date(item.scheduled_at), "dd/MM HH:mm")}</Badge> : null}
        </div>

        <p className="leading-7" dir={textDir(item.hebrew_draft || item.original_text)}>
          {item.hebrew_draft || item.original_text}
        </p>

        {href ? (
          <a href={href} target="_blank" rel="noreferrer" className="block truncate text-xs text-cyan-300 hover:underline" dir="ltr">
            {item.source_url}
          </a>
        ) : (
          <span className="block truncate text-xs text-[var(--muted)]" dir="ltr">
            {item.source_url}
          </span>
        )}

        <div className="flex flex-wrap gap-2">
          <Link href={`/create?edit=${item.id}`}>
            <Button variant="secondary">Edit</Button>
          </Link>
          <Button variant="secondary" disabled={copying} onClick={handleCopy}>
            {copying ? <><Loader2 size={14} className="animate-spin" /> Copying...</> : "Copy"}
          </Button>
          <Button variant="secondary" disabled={rescheduling} onClick={handleReschedule}>
            {rescheduling ? <><Loader2 size={14} className="animate-spin" /> Rescheduling...</> : "Reschedule"}
          </Button>
          <Button variant="danger" disabled={deleting} onClick={() => setConfirmDelete(true)}>
            Delete
          </Button>
        </div>

        <ConfirmDialog
          open={confirmDelete}
          title="Delete content"
          description="This will permanently remove this content item. This action cannot be undone."
          onConfirm={handleConfirmDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      </CardContent>
    </Card>
  );
}
