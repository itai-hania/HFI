"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, PenSquare, Download, ListTodo, Sparkles, LibraryBig, Settings, LogOut } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/create", label: "Create", icon: PenSquare },
  { href: "/acquire", label: "Acquire", icon: Download },
  { href: "/queue", label: "Queue", icon: ListTodo },
  { href: "/inspiration", label: "Inspiration", icon: Sparkles },
  { href: "/library", label: "Library", icon: LibraryBig },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({ onNavigate, onLogout }: { onNavigate?: () => void; onLogout: () => void }) {
  const pathname = usePathname();

  return (
    <aside className="surface-panel flex h-full w-80 flex-col border-r border-[var(--border)] px-4 py-6">
      <div className="mb-8 rounded-2xl border border-[var(--border)] bg-[rgba(255,255,255,0.02)] px-4 py-4">
        <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--muted)]">Hebrew FinTech</p>
        <h1 className="font-display mt-2 text-2xl font-semibold text-[var(--ink)]">Content Studio</h1>
        <p className="mt-2 text-xs text-[var(--muted)]">Editorial automation workspace</p>
      </div>

      <nav className="space-y-1.5">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "flex min-h-[44px] cursor-pointer items-center justify-between rounded-2xl border px-3.5 py-2.5 text-sm transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
                isActive
                  ? "border-[var(--accent)]/40 bg-[linear-gradient(135deg,rgba(236,72,153,0.28),rgba(236,72,153,0.16))] text-[var(--accent-ink)] shadow-[0_8px_24px_rgba(236,72,153,0.2)]"
                  : "border-transparent text-[var(--muted)] hover:border-[var(--border)] hover:bg-[var(--card-hover)] hover:text-[var(--ink)]",
              )}
            >
              <span className="flex items-center gap-2.5">
                <Icon size={16} />
                <span>{label}</span>
              </span>
              <span
                className={cn(
                  "size-1.5 rounded-full transition",
                  isActive ? "bg-[var(--accent-ink)]" : "bg-[transparent]",
                )}
                aria-hidden="true"
              />
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-[var(--border)] pt-4">
        <Button variant="secondary" className="w-full justify-between" onClick={onLogout}>
          Logout
          <LogOut size={16} />
        </Button>
      </div>
    </aside>
  );
}
