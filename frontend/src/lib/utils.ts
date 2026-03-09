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
