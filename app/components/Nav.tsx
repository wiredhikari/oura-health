"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/",         label: "Today" },
  { href: "/chat",     label: "Chat" },
  { href: "/log",      label: "Log" },
  { href: "/trends",   label: "Trends" },
  { href: "/digest",   label: "Digest" },
];

export function Nav() {
  const pathname = usePathname();
  // Hide nav on /login.
  if (pathname === "/login") return null;

  return (
    <header className="sticky top-0 z-30 backdrop-blur bg-bg/80 border-b border-border">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <span className="inline-flex h-7 w-7 rounded-lg bg-accent/15 text-accent items-center justify-center font-medium text-sm">
            O
          </span>
          <span className="font-medium">oura.health</span>
        </Link>

        <nav className="flex items-center gap-0.5 bg-muted rounded-full p-1">
          {TABS.map((t) => {
            const active =
              t.href === "/"
                ? pathname === "/"
                : pathname.startsWith(t.href);
            return (
              <Link
                key={t.href}
                href={t.href}
                className={
                  "px-3 py-1.5 text-sm rounded-full transition-colors " +
                  (active
                    ? "bg-surface border border-border"
                    : "text-subtle hover:text-text")
                }
              >
                {t.label}
              </Link>
            );
          })}
        </nav>

        <div className="hidden sm:flex h-7 w-7 rounded-full bg-muted items-center justify-center text-xs text-subtle font-medium">
          A
        </div>
      </div>
    </header>
  );
}
