"use client";
import * as React from "react";
import { BookOpen, Plus, Search, Database, RefreshCw, Download, FlaskConical, ShieldCheck, AlertTriangle, FileText } from "lucide-react";
import type { KnowledgeDocument, Page } from "@/types";
import { api, qs } from "@/services/api";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/components/providers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { EmptyState, PageHeader, Pagination, Skeleton, Spinner, Tabs } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { DocumentDetailDialog, EntryEditor, useCategories } from "@/components/documents/document-dialogs";
import { cn, label, timeAgo } from "@/lib/utils";

interface SearchResult { chunk_id: number; source_type: string; title: string; section: string | null; category: string; verified: boolean; content: string; relevance: number; vector_score: number; keyword_rank: number; version: number }

function Browse() {
  const { can } = useAuth();
  const categories = useCategories();
  const [category, setCategory] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [adding, setAdding] = React.useState(false);
  const [openId, setOpenId] = React.useState<number | null>(null);
  React.useEffect(() => setPage(1), [category]);
  const { data, loading, reload } = useApi<Page<KnowledgeDocument>>(`/documents${qs({ category, page, page_size: 15 })}`);
  return (
    <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
      <Card className="p-2 h-fit">
        <nav className="flex lg:flex-col gap-1 overflow-x-auto scrollbar-thin">
          {[{ value: "", label: "All knowledge" }, ...categories].map((c) => (
            <button key={c.value} onClick={() => setCategory(c.value)}
              className={cn("whitespace-nowrap rounded-md px-3 py-1.5 text-left text-sm", category === c.value ? "bg-primary text-primary-foreground" : "hover:bg-secondary text-muted-foreground")}>{c.label}</button>
          ))}
        </nav>
      </Card>
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div><CardTitle>{category ? label(category) : "All knowledge"}</CardTitle><CardDescription>Manual entries and uploaded documents</CardDescription></div>
          {can("admin") && <Button size="sm" onClick={() => setAdding(true)}><Plus />Add knowledge</Button>}
        </CardHeader>
        <CardContent>
          {loading && !data && <Skeleton className="h-40" />}
          {data?.items.length === 0 && <EmptyState icon={BookOpen} title="Nothing in this category yet" action={can("admin") && <Button size="sm" onClick={() => setAdding(true)}><Plus />Add knowledge</Button>} />}
          <div className="divide-y">
            {data?.items.map((d) => (
              <button key={d.id} onClick={() => setOpenId(d.id)} className="flex w-full items-start gap-3 py-3 text-left hover:bg-secondary/40 px-2 rounded-md">
                <FileText className="mt-0.5 size-4 shrink-0 text-primary" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><p className="font-medium text-sm">{d.title}</p>{d.status !== "published" && <StatusBadge status={d.status} />}{d.visibility === "restricted" && <StatusBadge status="restricted" />}</div>
                  <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{d.content_preview}</p>
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(d.updated_at)}</span>
              </button>
            ))}
          </div>
          {data && <Pagination page={page} pageSize={15} total={data.total} onChange={setPage} />}
        </CardContent>
      </Card>
      <EntryEditor open={adding} onClose={() => setAdding(false)} defaultCategory={category || undefined} onSaved={reload} />
      <DocumentDetailDialog id={openId} onClose={() => setOpenId(null)} onChanged={reload} />
    </div>
  );
}

function SearchTester() {
  const [q, setQ] = React.useState("");
  const [res, setRes] = React.useState<{ took_ms: number; results: SearchResult[]; detected_products: { name: string }[] } | null>(null);
  const [busy, setBusy] = React.useState(false);
  const run = async (e: React.FormEvent) => {
    e.preventDefault(); if (!q.trim()) return; setBusy(true);
    try { setRes(await api("/knowledge/search", { method: "POST", json: { query: q, top_k: 10 } })); } finally { setBusy(false); }
  };
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><FlaskConical className="size-4" />Retrieval tester</CardTitle><CardDescription>See exactly which knowledge BUI retrieves for a question (semantic + keyword hybrid search) and how relevant it is.</CardDescription></CardHeader>
      <CardContent>
        <form onSubmit={run} className="flex gap-2"><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type a question…" /><Button loading={busy}><Search />Search</Button></form>
        {res && (
          <div className="mt-4 space-y-2">
            <p className="text-xs text-muted-foreground">{res.results.length} results in {res.took_ms} ms{res.detected_products.length > 0 && <> · detected product: <b>{res.detected_products.map((p) => p.name).join(", ")}</b></>}</p>
            {res.results.map((r) => (
              <div key={r.chunk_id} className="rounded-lg border p-3">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium">{r.title}</span>{r.section && <Badge variant="secondary">{r.section}</Badge>}<Badge variant="outline">{r.source_type}</Badge>
                  {r.verified ? <Badge variant="success"><ShieldCheck />verified</Badge> : <Badge variant="warning"><AlertTriangle />research</Badge>}
                  <span className="ml-auto text-xs tabular-nums text-muted-foreground">relevance {(r.relevance * 100).toFixed(0)}% · vector {r.vector_score.toFixed(2)} · keyword {r.keyword_rank.toFixed(3)}</span>
                </div>
                <p className="mt-2 whitespace-pre-line text-xs text-muted-foreground line-clamp-4">{r.content}</p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function IndexPanel() {
  const { can } = useAuth();
  const toast = useToast();
  const { data, reload } = useApi<{ chunks_by_source: Record<string, number>; chunks_by_category: Record<string, number>; embedding_model: string }>("/knowledge/stats");
  const [busy, setBusy] = React.useState(false);
  const reindex = async () => {
    setBusy(true);
    try { const r = await api<{ took_ms: number }>("/knowledge/reindex", { method: "POST" }); toast.success("Index rebuilt", `Completed in ${(r.took_ms / 1000).toFixed(1)}s`); reload(); }
    catch (e) { toast.error("Re-index failed", (e as Error).message); } finally { setBusy(false); }
  };
  const exportJson = async () => {
    const data = await api("/admin/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `bui-knowledge-${new Date().toISOString().slice(0, 10)}.json`; a.click();
  };
  if (!data) return <Spinner />;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Database className="size-4" />Knowledge index</CardTitle><CardDescription>Embedding model: <code>{data.embedding_model}</code>{data.embedding_model.startsWith("hash") && " (fallback — install the sentence-transformers model for best semantic search)"}</CardDescription></CardHeader>
        <CardContent>
          <dl className="space-y-2 text-sm">{Object.entries(data.chunks_by_source).map(([k, v]) => <div key={k} className="flex justify-between"><dt className="capitalize text-muted-foreground">{k} chunks</dt><dd className="tabular-nums font-medium">{v}</dd></div>)}</dl>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="outline" onClick={reindex} loading={busy}><RefreshCw />Rebuild index</Button>
            {can("super_admin") && <Button variant="outline" onClick={exportJson}><Download />Export knowledge (JSON)</Button>}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">The index updates automatically on every change. Rebuild only after changing the embedding model.</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Chunks by category</CardTitle></CardHeader>
        <CardContent><dl className="space-y-2 text-sm">{Object.entries(data.chunks_by_category).sort((a, b) => b[1] - a[1]).map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-muted-foreground">{label(k)}</dt><dd className="tabular-nums font-medium">{v}</dd></div>)}</dl></CardContent>
      </Card>
    </div>
  );
}

export default function KnowledgePage() {
  const { can } = useAuth();
  const [tab, setTab] = React.useState<"browse" | "search" | "index">("browse");
  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-6">
      <PageHeader icon={BookOpen} title="Knowledge Base" description="Everything BUI knows, organised by category. Add company information, policies and notes here." />
      <Tabs className="mb-4" value={tab} onChange={setTab} tabs={[{ value: "browse", label: "Browse" }, { value: "search", label: "Search tester" }, ...(can("admin") ? [{ value: "index" as const, label: "Index" }] : [])]} />
      {tab === "browse" && <Browse />}
      {tab === "search" && <SearchTester />}
      {tab === "index" && <IndexPanel />}
    </div>
  );
}
