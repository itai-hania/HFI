"use client";

import { useRef, useEffect, useCallback } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ open, title, description, confirmLabel = "Delete", onConfirm, onCancel }: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  const handleClose = useCallback(() => {
    onCancel();
  }, [onCancel]);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      onClose={handleClose}
      className="fixed inset-0 z-50 m-auto w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--card)] p-0 text-[var(--ink)] shadow-[var(--shadow-lift)] backdrop:bg-black/60"
    >
      <div className="space-y-4 p-6">
        <div className="flex items-start gap-3">
          <div className="rounded-xl border border-red-900 bg-red-950/40 p-2.5">
            <AlertTriangle size={20} className="text-red-400" />
          </div>
          <div>
            <h3 className="font-display text-lg font-semibold">{title}</h3>
            <p className="mt-1 text-sm text-[var(--muted)]">{description}</p>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button variant="danger" onClick={onConfirm}>{confirmLabel}</Button>
        </div>
      </div>
    </dialog>
  );
}
