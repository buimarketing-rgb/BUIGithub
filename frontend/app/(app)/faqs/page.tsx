"use client";
import * as React from "react";
import { useSearchParams } from "next/navigation";
import { HelpCircle, Plus, Search, Pencil, Trash2, ChevronDown } from "lucide-react";
import type { FAQ, Page } from "@/types";
import { api, qs } from "@/services/api";
import { useApi, useDebounced } from "@/hooks/use-api";
import { useAuth } from "@/components/providers";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { useConfirm } from "@/components/ui/dialog";
import { EmptyState, ErrorBox, PageHeader, Pagination, Skeleton } from "@/components/ui/misc";
import { useProductOptions } from "@/components/documents/document-dialogs";
import { FAQEditor } from "@/components/faqs/faq-editor";
import { Markdown } from "@/components/chat/markdown";
import { cn } from "@/lib/utils";

function FaqsInner() {
  const { can } = useAuth();
  const confirm = useConfirm();
  const params = useSearchParams();
  const products = useProductOptions();
  const [q, setQ] = React.useState(params.get("q") || "");
  const [productId, setProductId] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [editing, setEditing] = React.useState<FAQ | null | undefined>(undefined);
  const [expanded, setExpanded] = React.useState<number | null>(null);
  const dq = useDebounced(q);
  React.useEffect(() => setPage(1), [dq, productId]);
  const { data, error, loading, reload } = useApi<Page<FAQ>>(`/faqs${qs({ q: dq, product_id: productId, page, page_size: 25 })}`);
  const remove = async (f: FAQ) => {
    if (!(await confirm({ title: "Delete FAQ?", description: f.question, confirmLabel: "Delete", destructive: true }))) return;
    await api(`/faqs/${f.id}`, { method: "DELETE" }); reload();
  };
  return (
    <div className="mx-auto max-w-5xl p-4 sm:p-6">
      <PageHeader icon={HelpCircle} title="FAQ Management" description="Approved answers to frequently asked questions. BUI prefers these when they match."
        actions={can("admin") && <Button onClick={() => setEditing(null)}><Plus />Add FAQ</Button>} />
      <div className="mb-4 grid gap-2 sm:grid-cols-[1fr_240px]">
        <div className="relative"><Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" /><Input className="pl-8" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search FAQs…" aria-label="Search FAQs" /></div>
        <Select value={productId} onChange={(e) => setProductId(e.target.value)} aria-label="Product"><option value="">All products</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select>
      </div>
      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && !data && <Skeleton className="h-40" />}
      {data?.items.length === 0 && <Card><EmptyState icon={HelpCircle} title="No FAQs found" action={can("admin") && <Button onClick={() => setEditing(null)}><Plus />Add FAQ</Button>} /></Card>}
      <div className="space-y-2">
        {data?.items.map((f) => (
          <Card key={f.id} className="overflow-hidden">
            <button className="flex w-full items-start gap-3 p-4 text-left" onClick={() => setExpanded(expanded === f.id ? null : f.id)} aria-expanded={expanded === f.id}>
              <HelpCircle className="mt-0.5 size-4 shrink-0 text-primary" />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-sm">{f.question}</p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {f.product_name && <Badge variant="secondary">{f.product_name}</Badge>}
                  {f.status !== "published" && <StatusBadge status={f.status} />}
                  {f.visibility === "restricted" && <StatusBadge status="restricted" />}
                  {f.origin === "unanswered_question" && <Badge variant="outline">from knowledge gap</Badge>}
                </div>
              </div>
              <ChevronDown className={cn("size-4 shrink-0 transition-transform", expanded === f.id && "rotate-180")} />
            </button>
            {expanded === f.id && (
              <div className="border-t bg-muted/30 px-4 py-3 pl-11">
                <Markdown content={f.answer} />
                {can("admin") && <div className="mt-2 flex gap-1"><Button size="sm" variant="ghost" onClick={() => setEditing(f)}><Pencil />Edit</Button><Button size="sm" variant="ghost" className="text-destructive" onClick={() => remove(f)}><Trash2 />Delete</Button></div>}
              </div>
            )}
          </Card>
        ))}
      </div>
      {data && <Pagination page={page} pageSize={25} total={data.total} onChange={setPage} />}
      <FAQEditor open={editing !== undefined} onClose={() => setEditing(undefined)} faq={editing} onSaved={reload} />
    </div>
  );
}

export default function FaqsPage() { return <React.Suspense><FaqsInner /></React.Suspense>; }
