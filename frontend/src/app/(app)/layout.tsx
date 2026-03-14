"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { useAuth } from "@/hooks/useAuth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const authed = isAuthenticated();

  useEffect(() => {
    if (!authed) {
      router.replace("/login");
    }
  }, [authed, router]);

  if (!authed) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center px-4">
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/70 px-5 py-4 text-sm text-[var(--muted)]">
          Loading workspace...
        </div>
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}
