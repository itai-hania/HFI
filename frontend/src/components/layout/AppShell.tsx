"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, PenSquare } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";

import { Sidebar } from "@/components/layout/Sidebar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";

function getPageMeta(pathname: string) {
  if (pathname.startsWith("/create")) {
    return { title: "Create", description: "Craft and polish Hebrew copy with controlled workflow." };
  }
  if (pathname.startsWith("/queue")) {
    return { title: "Queue", description: "Review drafts, schedule approved content, and monitor publication states." };
  }
  if (pathname.startsWith("/inspiration")) {
    return { title: "Inspiration", description: "Harvest high-signal posts and convert them into production-ready content." };
  }
  if (pathname.startsWith("/library")) {
    return { title: "Library", description: "Explore historical outputs and reusable language assets." };
  }
  if (pathname.startsWith("/settings")) {
    return { title: "Settings", description: "Tune preferences, style controls, and account-level behavior." };
  }
  return { title: "Dashboard", description: "Daily command center for briefs, schedule, and throughput." };
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const { logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const meta = getPageMeta(pathname);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <div className="relative flex min-h-screen">
      <div className="hidden md:sticky md:top-0 md:block md:h-screen">
        <Sidebar onLogout={handleLogout} />
      </div>

      {open ? (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-black/60"
            aria-label="Close menu"
          />
          <div className="absolute right-0 top-0 h-full w-80 max-w-[88vw]">
            <Sidebar onLogout={handleLogout} onNavigate={() => setOpen(false)} />
          </div>
        </div>
      ) : null}

      <main className="min-h-screen flex-1 px-4 pb-8 pt-4 md:px-8 md:pb-10 md:pt-6">
        <div className="mx-auto w-full max-w-[1320px] space-y-6">
          <header className="surface-panel sticky top-2 z-30 rounded-2xl px-4 py-3 md:px-5 md:py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--muted)]">HFI v2</p>
                <h1 className="font-display mt-1 text-2xl leading-tight">{meta.title}</h1>
                <p className="mt-1 text-sm text-[var(--muted)]">{meta.description}</p>
              </div>

              <div className="flex items-center gap-2">
                <Link href="/create">
                  <Button>
                    <PenSquare size={16} />
                    New Draft
                  </Button>
                </Link>
                <Button variant="secondary" onClick={() => setOpen(true)} className="md:hidden">
                  <Menu size={16} />
                  Menu
                </Button>
              </div>
            </div>
          </header>

          <div className="section-fade">{children}</div>
        </div>
      </main>
    </div>
  );
}
