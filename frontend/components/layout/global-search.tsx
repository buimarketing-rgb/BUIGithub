"use client";
import * as React from "react";
import Link from "next/link";
import { BookOpen, HelpCircle, Package, Globe, Search, MessageSquareText } from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { api } from "@/services/api";
import { useDebounced } from "@/hooks/use-api";
import { Spinner } from "@/components/ui/misc";
import { Badge } from "@/components/ui/badge";

interface Result { chunk_id: number; source_type: string; source_id: number; product_id: number | null; title: string; section: string | null; content: string; relevance: number; verified: boolean }

const ICON: Record<string, React.ElementType> = { product: Package, document: BookOpen, faq: HelpCircle, research: Globe };
function href(r: Result) {
  if (r.source_type === "product") return `/products/${r.source_id}`;
  if (r.source_type === "document") return `/documents?open=${r.source_id}`;
  if (r.source_type === "faq") return `/faqs?q=${encodeURIComponent(r.title.replace(/^FAQ: /, ""))}`;
  return r.product_id ? `/products/${r.product_id}` : "/knowledge";
}

export function GlobalSearch({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = React.useState("");
  const dq = useDebounced(q, 250);
  const [results, setResults] = React.useState<Result[]>([]);
  const [loading, setLoading] = React.useState(false);
  React.useEffect(() => {
    if (!open || dq.trim().length < 2) { setResults([]); return; }
    setLoading(true);
    api<{ results: Result[] }>("/knowledge/search", { method: "POST", json: { query: dq, top_k: 10 } })
      .then((r) => setResults(r.results)).catch(() => setResults([])).finally(() => setLoading(false));
  }, [dq, open]);
  return (
    <Dialog open={open} onClose={onClose} title="Search the knowledge base" description="Hybrid semantic + keyword search across products, documents, FAQs and approved research." size="lg">
      <div className="relative">
        <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. warranty of AF-500, installation, error E07…"
          className="h-10 w-full rounded-md border bg-background pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
      </div>
      <div className="mt-4 space-y-2 min-h-24">
        {loading && <Spinner />}
        {!loading && dq.length >= 2 && results.length === 0 && <p className="text-sm text-muted-foreground">No matching knowledge found.</p>}
        {results.map((r) => {
          const Icon = ICON[r.source_type] || BookOpen;
          return (
            <Link key={r.chunk_id} href={href(r)} onClick={onClose} className="flex gap-3 rounded-lg border p-3 hover:bg-secondary transition-colors">
              <Icon className="size-4 mt-0.5 text-primary shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium text-sm truncate">{r.title}</p>
                  {r.section && <Badge variant="secondary">{r.section}</Badge>}
                  {!r.verified && <Badge variant="warning">research</Badge>}
                </div>
                <p className="text-xs text-muted-foreground line-clamp-2 mt-1">{r.content}</p>
              </div>
            </Link>
          );
        })}
        {q.trim().length > 3 && (
          <Link href={`/assistant?q=${encodeURIComponent(q)}`} onClick={onClose} className="flex items-center gap-2 rounded-lg p-3 text-sm text-primary hover:bg-accent">
            <MessageSquareText className="size-4" /> Ask BUI: “{q}”
          </Link>
        )}
      </div>
    </Dialog>
  );
}
