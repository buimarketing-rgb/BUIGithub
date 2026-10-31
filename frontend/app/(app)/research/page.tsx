"use client";
import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Globe, Search, Link2, Package, CalendarClock, ShieldAlert } from "lucide-react";
import type { Page, ResearchJob } from "@/types";
import { api, qs } from "@/services/api";
import { useApi } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { EmptyState, ErrorBox, PageHeader, Pagination, Table, Td, Th, Tabs } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { useProductOptions } from "@/components/documents/document-dialogs";
import { timeAgo } from "@/lib/utils";

function ResearchInner() {
  const router = useRouter();
  const params = useSearchParams();
  const toast = useToast();
  const products = useProductOptions();
  const [mode, setMode] = React.useState<"product" | "query" | "url">(params.get("q") ? "query" : "product");
  const [productId, setProductId] = React.useState("");
  const [query, setQuery] = React.useState(params.get("q") || "");
  const [url, setUrl] = React.useState("");
  const [schedule, setSchedule] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [status, setStatus] = React.useState("");
  const [page, setPage] = React.useState(1);
  const { data, error, reload } = useApi<Page<ResearchJob>>(`/research/jobs${qs({ status, page, page_size: 20 })}`);

  React.useEffect(() => {
    if (!data?.items.some((j) => ["queued", "running"].includes(j.status))) return;
    const t = setTimeout(reload, 2500);
    return () => clearTimeout(t);
  }, [data, reload]);

  const start = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const body = { product_id: productId ? Number(productId) : null, query: mode === "query" ? query : null, url: mode === "url" ? url : null, schedule_hours: schedule ? Number(schedule) : null };
      const job = await api<ResearchJob>("/research/jobs", { method: "POST", json: body });
      toast.success("Research started", "BUI is searching official and public sources.");
      router.push(`/research/${job.id}`);
    } catch (err) { toast.error("Could not start research", (err as Error).message); } finally { setBusy(false); }
  };

  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-6">
      <PageHeader icon={Globe} title="Online Research" description="Gather product information from manufacturer sites and public pages. Nothing is added to company knowledge until you approve it." />
      <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
        <Card className="h-fit">
          <CardHeader><CardTitle>New research</CardTitle><CardDescription>Official manufacturer websites are prioritised. robots.txt and access restrictions are always respected.</CardDescription></CardHeader>
          <CardContent>
            <form onSubmit={start} className="space-y-4">
              <Tabs value={mode} onChange={setMode} tabs={[{ value: "product", label: "Product", icon: Package }, { value: "query", label: "Name", icon: Search }, { value: "url", label: "URL", icon: Link2 }]} />
              <Field label={mode === "product" ? "Product" : "Link findings to product (optional)"}>
                <Select value={productId} onChange={(e) => setProductId(e.target.value)} required={mode === "product"}>
                  <option value="">{mode === "product" ? "Choose a product…" : "— None —"}</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </Select>
              </Field>
              {mode === "query" && <Field label="Product name or search terms"><Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. Grundfos SCALA2 specifications" required /></Field>}
              {mode === "url" && <Field label="Page URL" hint="A public product, specification or manual page."><Input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://manufacturer.com/product" required /></Field>}
              <Field label="Repeat automatically" hint="Scheduled research re-checks sources and queues only new findings.">
                <Select value={schedule} onChange={(e) => setSchedule(e.target.value)}>
                  <option value="">Manual only</option><option value="24">Daily</option><option value="168">Weekly</option><option value="720">Monthly</option>
                </Select>
              </Field>
              <Button className="w-full" loading={busy}><Globe />Start research</Button>
              <p className="flex gap-2 text-xs text-muted-foreground"><ShieldAlert className="size-4 shrink-0" />Research results are always marked unverified and never overwrite verified company data automatically.</p>
            </form>
          </CardContent>
        </Card>
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="font-semibold">Research activity</h2>
            <Select className="w-40" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Status">
              <option value="">All statuses</option><option value="completed">Completed</option><option value="running">Running</option><option value="failed">Failed</option>
            </Select>
          </div>
          {error && <ErrorBox message={error} onRetry={reload} />}
          {data?.items.length === 0 && <EmptyState icon={Globe} title="No research yet" description="Start by researching one of your products." />}
          {!!data?.items.length && (
            <Table>
              <thead><tr><Th>Research</Th><Th>Status</Th><Th>Findings</Th><Th className="hidden md:table-cell">When</Th></tr></thead>
              <tbody>{data.items.map((j) => (
                <tr key={j.id} className="cursor-pointer hover:bg-secondary/50" onClick={() => router.push(`/research/${j.id}`)}>
                  <Td>
                    <Link href={`/research/${j.id}`} className="font-medium hover:text-primary">{j.query || j.url || j.product_name || `Job #${j.id}`}</Link>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {j.product_name && <Badge variant="secondary">{j.product_name}</Badge>}
                      <Badge variant="outline">{j.origin}</Badge>
                      {j.schedule_hours && <Badge variant="outline"><CalendarClock />every {j.schedule_hours >= 168 ? `${Math.round(j.schedule_hours / 168)}w` : `${j.schedule_hours}h`}</Badge>}
                    </div>
                  </Td>
                  <Td><StatusBadge status={j.status} /></Td>
                  <Td><div className="flex flex-wrap gap-1">
                    {!!j.finding_counts.pending && <Badge variant="warning">{j.finding_counts.pending} pending</Badge>}
                    {!!j.finding_counts.conflicts && <Badge variant="destructive">{j.finding_counts.conflicts} conflicts</Badge>}
                    {!!j.finding_counts.approved && <Badge variant="success">{j.finding_counts.approved} approved</Badge>}
                    {!j.finding_counts.pending && !j.finding_counts.approved && <span className="text-xs text-muted-foreground">—</span>}
                  </div></Td>
                  <Td className="hidden md:table-cell whitespace-nowrap text-xs text-muted-foreground">{timeAgo(j.last_run_at || j.created_at)}</Td>
                </tr>
              ))}</tbody>
            </Table>
          )}
          {data && <Pagination page={page} pageSize={20} total={data.total} onChange={setPage} />}
        </Card>
      </div>
    </div>
  );
}

export default function ResearchPage() { return <React.Suspense><ResearchInner /></React.Suspense>; }
