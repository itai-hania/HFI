"use client";

import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { InspirationPost } from "@/lib/types";

function safeHref(value: string | null | undefined) {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

export function PostCard({ post }: { post: InspirationPost }) {
  const router = useRouter();
  const href = safeHref(post.post_url);

  return (
    <Card className="lift-hover">
      <CardContent className="space-y-3 py-4">
        <p className="text-sm leading-6 text-left text-[var(--ink)]" dir="ltr">
          {post.content}
        </p>

        <div className="flex flex-wrap gap-2">
          <Badge>{post.likes.toLocaleString()} likes</Badge>
          <Badge>{post.retweets.toLocaleString()} reposts</Badge>
          <Badge>{post.views.toLocaleString()} views</Badge>
        </div>

        <div className="flex gap-2">
          <Button
            onClick={() =>
              router.push(`/create?source=inspiration&text=${encodeURIComponent(post.content || "")}`)
            }
          >
            Use as Source
          </Button>
          {href ? (
            <a href={href} target="_blank" rel="noreferrer">
              <Button variant="secondary">Open X Post</Button>
            </a>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
