import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const HEBREW_RANGE = /[\u0590-\u05FF]/g;

/**
 * Returns true when more than 30% of alphabetic characters are Hebrew.
 * Used to decide whether a text block should render RTL.
 */
export function isHebrew(text: string | null | undefined): boolean {
  if (!text) return false;
  const letters = text.replace(/[^a-zA-Z\u0590-\u05FF]/g, "");
  if (letters.length === 0) return false;
  const hebrewMatches = text.match(HEBREW_RANGE);
  return (hebrewMatches?.length ?? 0) / letters.length > 0.3;
}

/**
 * Returns "rtl" for Hebrew-heavy text, "ltr" otherwise.
 */
export function textDir(text: string | null | undefined): "rtl" | "ltr" {
  return isHebrew(text) ? "rtl" : "ltr";
}

/**
 * Converts a timestamp (ms since epoch or ISO string) into a short relative label.
 * E.g. "2m ago", "1h ago", "3d ago".
 */
export function formatRelativeTime(timestamp: number | string): string {
  const ms = typeof timestamp === "string" ? new Date(timestamp).getTime() : timestamp;
  if (Number.isNaN(ms)) return "";
  const diffMs = Date.now() - ms;
  if (diffMs < 0) return "just now";
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
