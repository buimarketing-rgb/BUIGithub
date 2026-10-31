"use client";
import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Menu, Moon, Sun, Monitor, Search, X, ShieldCheck } from "lucide-react";
import { useAuth, useTheme } from "@/components/providers";
import { NAV } from "./nav";
import { Logo } from "./logo";
import { cn, ROLE_LABEL } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { GlobalSearch } from "./global-search";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout, can } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [searchOpen, setSearchOpen] = React.useState(false);
  const { theme, setTheme } = useTheme();

  React.useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, router, pathname]);
  React.useEffect(() => setOpen(false), [pathname]);
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setSearchOpen(true); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (loading || !user) return <div className="grid h-screen place-items-center"><Spinner className="size-8" /></div>;
  const items = NAV.filter((n) => can(n.role));
  const nextTheme = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
  const ThemeIcon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;

  const sidebar = (
    <nav className="flex h-full flex-col">
      <div className="flex h-16 items-center justify-between px-4 border-b">
        <Link href="/assistant"><Logo /></Link>
        <Button variant="ghost" size="icon-sm" className="lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu"><X /></Button>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-0.5">
        {items.map((n) => {
          const active = pathname === n.href || pathname.startsWith(n.href + "/");
          return (
            <Link key={n.href} href={n.href}
              className={cn("flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-secondary hover:text-foreground")}>
              <n.icon className="size-4" />{n.label}
            </Link>
          );
        })}
      </div>
      <div className="border-t p-3">
        <div className="flex items-center gap-3 rounded-lg p-2">
          <div className="grid size-9 place-items-center rounded-full bg-gradient-to-br from-brandred to-primary text-white text-sm font-semibold">
            {user.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{user.full_name}</p>
            <p className="truncate text-xs text-muted-foreground flex items-center gap-1">{user.role !== "team_member" && <ShieldCheck className="size-3" />}{ROLE_LABEL[user.role]}</p>
          </div>
          <Button variant="ghost" size="icon-sm" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut /></Button>
        </div>
      </div>
    </nav>
  );

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="hidden lg:block w-64 shrink-0 border-r bg-sidebar">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-sidebar shadow-xl animate-fade-in">{sidebar}</aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-card/80 backdrop-blur px-3 sm:px-5">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu /></Button>
          <button onClick={() => setSearchOpen(true)}
            className="flex h-9 flex-1 max-w-md items-center gap-2 rounded-md border bg-background px-3 text-sm text-muted-foreground hover:bg-secondary transition-colors">
            <Search className="size-4" /><span className="truncate">Search knowledge…</span>
            <kbd className="ml-auto hidden sm:inline rounded border bg-muted px-1.5 text-[10px]">Ctrl K</kbd>
          </button>
          <div className="ml-auto flex items-center gap-1">
            <Button variant="ghost" size="icon" onClick={() => setTheme(nextTheme)} aria-label={`Theme: ${theme}`} title={`Theme: ${theme}`}><ThemeIcon /></Button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto scrollbar-thin">{children}</main>
      </div>
      <GlobalSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
