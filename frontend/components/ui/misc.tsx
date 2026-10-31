"use client";
import * as React from "react";
import { ChevronLeft, ChevronRight, Loader2, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./button";

export const Spinner = ({ className }: { className?: string }) => <Loader2 className={cn("size-5 animate-spin text-muted-foreground", className)} />;

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} />;
}

export function PageHeader({ title, description, actions, icon: Icon }: { title: string; description?: string; actions?: React.ReactNode; icon?: React.ElementType }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between mb-6">
      <div className="flex items-start gap-3">
        {Icon && <div className="hidden sm:grid place-items-center size-10 rounded-lg bg-accent text-accent-foreground"><Icon className="size-5" /></div>}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {description && <p className="text-sm text-muted-foreground mt-1 max-w-2xl">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, description, action }: { icon: React.ElementType; title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-14 px-4">
      <div className="grid place-items-center size-12 rounded-full bg-muted mb-4"><Icon className="size-6 text-muted-foreground" /></div>
      <p className="font-medium">{title}</p>
      {description && <p className="text-sm text-muted-foreground mt-1 max-w-sm">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
      <AlertTriangle className="size-5 text-destructive shrink-0" />
      <p className="flex-1">{message}</p>
      {onRetry && <Button size="sm" variant="outline" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function Pagination({ page, pageSize, total, onChange }: { page: number; pageSize: number; total: number; onChange: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  return (
    <div className="flex items-center justify-between gap-2 pt-4 text-sm text-muted-foreground">
      <span>{(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}</span>
      <div className="flex gap-1">
        <Button variant="outline" size="icon-sm" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Previous page"><ChevronLeft /></Button>
        <span className="px-2 py-1">{page} / {pages}</span>
        <Button variant="outline" size="icon-sm" disabled={page >= pages} onClick={() => onChange(page + 1)} aria-label="Next page"><ChevronRight /></Button>
      </div>
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange, className }: { tabs: { value: T; label: string; icon?: React.ElementType; count?: number }[]; value: T; onChange: (v: T) => void; className?: string }) {
  return (
    <div role="tablist" className={cn("inline-flex max-w-full overflow-x-auto scrollbar-thin rounded-lg bg-muted p-1 gap-1", className)}>
      {tabs.map((t) => (
        <button key={t.value} role="tab" aria-selected={value === t.value} onClick={() => onChange(t.value)}
          className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            value === t.value ? "bg-card shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground")}>
          {t.icon && <t.icon className="size-4" />}{t.label}
          {t.count !== undefined && <span className="rounded-full bg-secondary px-1.5 text-[11px]">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Table({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("w-full overflow-x-auto", className)}><table className="w-full text-sm">{children}</table></div>;
}
export const Th = ({ children, className }: { children?: React.ReactNode; className?: string }) => <th className={cn("h-10 px-3 text-left align-middle text-xs font-medium uppercase tracking-wide text-muted-foreground border-b whitespace-nowrap", className)}>{children}</th>;
export const Td = ({ children, className, ...p }: React.TdHTMLAttributes<HTMLTableCellElement>) => <td className={cn("px-3 py-3 align-middle border-b", className)} {...p}>{children}</td>;

/** Editable list of strings (features, accessories...) */
export function ListEditor({ value, onChange, placeholder }: { value: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [draft, setDraft] = React.useState("");
  const add = () => { const v = draft.trim(); if (v) { onChange([...value, v]); setDraft(""); } };
  return (
    <div className="space-y-2">
      {value.map((item, i) => (
        <div key={i} className="flex gap-2">
          <input className="flex-1 h-8 rounded-md border border-input bg-card px-2 text-sm" value={item}
            onChange={(e) => onChange(value.map((x, j) => (j === i ? e.target.value : x)))} />
          <Button type="button" variant="ghost" size="icon-sm" onClick={() => onChange(value.filter((_, j) => j !== i))} aria-label="Remove">×</Button>
        </div>
      ))}
      <div className="flex gap-2">
        <input className="flex-1 h-8 rounded-md border border-dashed border-input bg-transparent px-2 text-sm" placeholder={placeholder || "Add item and press Enter"}
          value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
        <Button type="button" variant="outline" size="sm" onClick={add}>Add</Button>
      </div>
    </div>
  );
}
