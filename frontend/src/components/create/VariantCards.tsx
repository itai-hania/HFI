"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Variant } from "@/lib/types";

function qualityStyle(score: number) {
  if (score >= 85) return "border-emerald-400/40 text-emerald-300";
  if (score >= 70) return "border-cyan-400/40 text-cyan-300";
  if (score >= 50) return "border-amber-400/40 text-amber-300";
  return "border-rose-400/40 text-rose-300";
}

export function VariantCards({
  variants,
  selectedIndex,
  onSelect,
}: {
  variants: Variant[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}) {
  if (variants.length === 0) {
    return <p className="text-sm text-[var(--muted)]">Generate variants to continue.</p>;
  }

  return (
    <div className="grid gap-3 xl:grid-cols-3">
      {variants.map((variant, index) => (
        <Card
          key={`${variant.angle}-${index}`}
          className={selectedIndex === index ? "lift-hover border-[var(--accent)]/60 shadow-[0_14px_34px_rgba(236,72,153,0.2)]" : "lift-hover"}
        >
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <CardTitle>{variant.label}</CardTitle>
              <Badge className={qualityStyle(variant.quality_score)}>{variant.quality_score}/100</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="line-clamp-4 min-h-20 text-sm leading-7" dir="rtl">
              {variant.content}
            </p>
            <div className="flex items-center justify-between text-xs text-[var(--muted)]">
              <span>{variant.char_count} chars</span>
              <span>{variant.is_valid_hebrew ? "Hebrew OK" : "Needs edit"}</span>
            </div>
            <Button className="w-full" variant={selectedIndex === index ? "primary" : "secondary"} onClick={() => onSelect(index)}>
              {selectedIndex === index ? "Selected" : "Select"}
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
