"use client";
import * as React from "react";
import { MessageSquarePlus, Search, Trash2, Pencil, Mic, Check, X } from "lucide-react";
import type { Conversation, Page } from "@/types";
import { api, qs } from "@/services/api";
import { useApi, useDebounced } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { useConfirm } from "@/components/ui/dialog";
import { cn, timeAgo } from "@/lib/utils";

export function ChatHistory({ activeId, onSelect, onNew, refreshKey }: { activeId: number | null; onSelect: (id: number) => void; onNew: () => void; refreshKey: number }) {
  const [q, setQ] = React.useState("");
  const dq = useDebounced(q);
  const { data, loading, reload } = useApi<Page<Conversation>>(`/chat/conversations${qs({ q: dq, page_size: 60 })}`, [refreshKey]);
  const confirm = useConfirm();
  const [editing, setEditing] = React.useState<number | null>(null);
  const [title, setTitle] = React.useState("");

  const remove = async (c: Conversation) => {
    if (!(await confirm({ title: "Delete conversation?", description: `“${c.title}” will be permanently deleted.`, confirmLabel: "Delete", destructive: true }))) return;
    await api(`/chat/conversations/${c.id}`, { method: "DELETE" });
    if (c.id === activeId) onNew();
    reload();
  };
  const rename = async (id: number) => {
    if (title.trim()) await api(`/chat/conversations/${id}`, { method: "PATCH", json: { title } });
    setEditing(null);
    reload();
  };

  return (
    <div className="flex h-full flex-col">
      <div className="space-y-2 p-3">
        <Button className="w-full justify-start" variant="outline" onClick={onNew}><MessageSquarePlus />New chat</Button>
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search conversations" aria-label="Search conversations"
            className="h-8 w-full rounded-md border bg-background pl-8 pr-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring" />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin px-2 pb-3">
        {loading && !data && <div className="p-4"><Spinner /></div>}
        {data?.items.length === 0 && <p className="px-3 py-6 text-center text-xs text-muted-foreground">{dq ? "No matching conversations." : "No conversations yet."}</p>}
        {data?.items.map((c) => (
          <div key={c.id} className={cn("group relative rounded-md", c.id === activeId ? "bg-secondary" : "hover:bg-secondary/60")}>
            {editing === c.id ? (
              <div className="flex items-center gap-1 p-1.5">
                <input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === "Enter" && rename(c.id)}
                  className="h-7 flex-1 rounded border bg-background px-2 text-xs" aria-label="Conversation title" />
                <Button size="icon-sm" variant="ghost" onClick={() => rename(c.id)} aria-label="Save"><Check /></Button>
                <Button size="icon-sm" variant="ghost" onClick={() => setEditing(null)} aria-label="Cancel"><X /></Button>
              </div>
            ) : (
              <button onClick={() => onSelect(c.id)} className="w-full px-3 py-2 text-left">
                <p className="flex items-center gap-1.5 truncate pr-12 text-sm">{c.is_voice && <Mic className="size-3 shrink-0 text-brandred" />}<span className="truncate">{c.title}</span></p>
                {c.snippet ? <p className="truncate text-[11px] text-muted-foreground">{c.snippet}</p> : <p className="text-[11px] text-muted-foreground">{timeAgo(c.updated_at)}</p>}
              </button>
            )}
            {editing !== c.id && (
              <div className="absolute right-1 top-1.5 hidden gap-0.5 group-hover:flex">
                <Button size="icon-sm" variant="ghost" onClick={() => { setEditing(c.id); setTitle(c.title); }} aria-label="Rename"><Pencil /></Button>
                <Button size="icon-sm" variant="ghost" onClick={() => remove(c)} aria-label="Delete"><Trash2 /></Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
