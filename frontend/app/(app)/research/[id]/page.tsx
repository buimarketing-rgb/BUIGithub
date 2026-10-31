"use client";
import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw, Trash2, Check, X, ShieldCheck, AlertTriangle, Copy as DupIcon, ExternalLink, Ban, CalendarClock } from "lucide-react";
import type { ResearchJobDetail } from "@/types";
import { api } from "@/services/api";
import { useApi } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input, Select, Switch } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { ErrorBox, Skeleton, Tabs, Table, Td, Th, EmptyState, Spinner } from "@/components/ui/misc";
import { useConfirm } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { formatDate, cn } from "@/lib/utils";

export default function ResearchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const confirm = useConfirm();
  const { data: job, error, reload, setData } = useApi<ResearchJobDetail>(`/research/jobs/${id}`);
  const [filter, setFilter] = React.useState<"pending" | "conflicts" | "all">("pending");
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [applyToProduct, setApplyToProduct] = React.useState(true);
  const [replaceConflicts, setReplaceConflicts] = React.useState(false);
  const [note, setNote] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [tab, setTab] = React.useState<"findings" | "sources" | "log">("findings");

  React.useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const t = setTimeout(reload, 2000);
    return () => clearTimeout(t);
  }, [job, reload]);

  if (error) return <div className="p-6"><ErrorBox message={error} onRetry={reload} /></div>;
  if (!job) return <div className="mx-auto max-w-6xl space-y-4 p-6"><Skeleton className="h-10 w-80" /><Skeleton className="h-64" /></div>;

  const findings = job.findings.filter((f) => filter === "all" || (filter === "pending" ? f.status === "pending" : f.has_conflict && f.status === "pending"));
  const toggle = (fid: number) => setSelected((s) => { const n = new Set(s); n.has(fid) ? n.delete(fid) : n.add(fid); return n; });
  const allPendingIds = findings.filter((f) => f.status === "pending").map((f) => f.id);

  const review = async (action: "approve" | "reject", ids = Array.from(selected)) => {
    if (!ids.length) return;
    if (action === "approve" && replaceConflicts && !(await confirm({ title: "Replace verified values?", description: "Conflicting findings will overwrite the verified product values. A new product version is created so you can restore the old values.", confirmLabel: "Approve & replace", destructive: true }))) return;
    setBusy(true);
    try {
      const r = await api<{ results: { id: number; result: string }[] }>("/research/findings/review", { method: "POST", json: { finding_ids: ids, action, apply_to_product: applyToProduct, replace_conflicts: replaceConflicts, note: note || null } });
      toast.success(`${action === "approve" ? "Approved" : "Rejected"} ${ids.length} finding${ids.length > 1 ? "s" : ""}`, r.results[0]?.result);
      setSelected(new Set()); setNote(""); reload();
    } catch (e) { toast.error("Review failed", (e as Error).message); } finally { setBusy(false); }
  };
  const rerun = async () => { try { await api(`/research/jobs/${job.id}/run`, { method: "POST" }); toast.info("Research refresh started"); reload(); } catch (e) { toast.error((e as Error).message); } };
  const remove = async () => {
    if (!(await confirm({ title: "Delete this research job?", description: "Approved findings that were added to the knowledge base as research will also be removed. Changes already applied to products stay.", confirmLabel: "Delete", destructive: true }))) return;
    await api(`/research/jobs/${job.id}`, { method: "DELETE" }); router.push("/research");
  };
  const setSchedule = async (v: string) => {
    setData(await api(`/research/jobs/${job.id}`, { method: "PATCH", json: v ? { schedule_hours: Number(v) } : { clear_schedule: true } }) as ResearchJobDetail & never);
    reload();
  };

  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-6">
      <Link href="/research" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" />Online Research</Link>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2"><h1 className="text-2xl font-semibold tracking-tight">{job.query || job.url || job.product_name || `Research #${job.id}`}</h1><StatusBadge status={job.status} /></div>
          <p className="mt-1 text-sm text-muted-foreground">
            {job.product_name && <>Product: <Link className="text-primary hover:underline" href={`/products/${job.product_id}`}>{job.product_name}</Link> · </>}
            Started by {job.origin} · last run {formatDate(job.last_run_at || job.created_at, true)}
            {job.next_run_at && <> · next run {formatDate(job.next_run_at, true)}</>}
          </p>
          {job.error && <p className="mt-2 text-sm text-destructive">{job.error}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5"><CalendarClock className="size-4 text-muted-foreground" />
            <Select className="h-9 w-36" value={job.schedule_hours ? String(job.schedule_hours) : ""} onChange={(e) => setSchedule(e.target.value)} aria-label="Schedule">
              <option value="">Manual only</option><option value="24">Daily</option><option value="168">Weekly</option><option value="720">Monthly</option>
            </Select></div>
          <Button variant="outline" onClick={rerun} disabled={["queued", "running"].includes(job.status)}><RefreshCw className={cn(job.status === "running" && "animate-spin")} />Refresh</Button>
          <Button variant="ghost" size="icon" onClick={remove} aria-label="Delete job"><Trash2 className="text-destructive" /></Button>
        </div>
      </div>

      {["queued", "running"].includes(job.status) && <Card className="mt-4 flex items-center gap-3 p-4 text-sm"><Spinner />Researching… {job.log.at(-1)?.msg}</Card>}

      <Tabs className="mt-6" value={tab} onChange={setTab} tabs={[{ value: "findings", label: "Findings", count: job.findings.length }, { value: "sources", label: "Sources", count: job.sources.length }, { value: "log", label: "Activity log" }]} />

      {tab === "findings" && (
        <Card className="mt-4">
          <CardHeader className="gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Tabs value={filter} onChange={(v) => { setFilter(v); setSelected(new Set()); }} tabs={[
                { value: "pending", label: "Pending review", count: job.findings.filter((f) => f.status === "pending").length },
                { value: "conflicts", label: "Conflicts", count: job.findings.filter((f) => f.has_conflict && f.status === "pending").length },
                { value: "all", label: "All" },
              ]} />
              <div className="flex flex-wrap items-center gap-4 text-sm">
                <label className="flex items-center gap-2"><Switch checked={applyToProduct} onChange={setApplyToProduct} label="Apply to product" />Apply to product</label>
                <label className="flex items-center gap-2"><Switch checked={replaceConflicts} onChange={setReplaceConflicts} label="Replace conflicting values" />Replace conflicts</label>
              </div>
            </div>
            {selected.size > 0 && (
              <div className="flex flex-wrap items-center gap-2 rounded-lg bg-accent p-2">
                <span className="px-2 text-sm font-medium">{selected.size} selected</span>
                <Input className="h-8 max-w-xs flex-1" placeholder="Review note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
                <Button size="sm" onClick={() => review("approve")} loading={busy}><Check />Approve</Button>
                <Button size="sm" variant="outline" onClick={() => review("reject")} disabled={busy}><X />Reject</Button>
              </div>
            )}
          </CardHeader>
          <CardContent>
            {findings.length === 0 ? <EmptyState icon={ShieldCheck} title={filter === "pending" ? "Nothing waiting for review" : "No findings"} description={job.status === "completed" && job.findings.length === 0 ? "No structured information could be extracted from the accessible sources." : undefined} /> : (
              <Table>
                <thead><tr>
                  <Th><input type="checkbox" aria-label="Select all" checked={allPendingIds.length > 0 && allPendingIds.every((i) => selected.has(i))} onChange={(e) => setSelected(e.target.checked ? new Set(allPendingIds) : new Set())} /></Th>
                  <Th>Finding</Th><Th>Source</Th><Th>Flags</Th><Th /></tr></thead>
                <tbody>{findings.map((f) => (
                  <tr key={f.id} className={cn(f.has_conflict && f.status === "pending" && "bg-destructive/5")}>
                    <Td>{f.status === "pending" && <input type="checkbox" aria-label="Select finding" checked={selected.has(f.id)} onChange={() => toggle(f.id)} />}</Td>
                    <Td className="max-w-md">
                      <Badge variant="outline" className="mb-1 capitalize">{f.category}</Badge>
                      <p className="text-sm">{f.key && <span className="font-medium">{f.key}: </span>}{f.value}</p>
                      {f.conflict_with && <p className="mt-1 text-xs text-destructive">{f.conflict_with}</p>}
                      {f.review_note && <p className="mt-1 text-xs text-muted-foreground">Note: {f.review_note}</p>}
                    </Td>
                    <Td className="text-xs">
                      {f.source_url ? <a href={f.source_url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-primary hover:underline">{f.source_domain}<ExternalLink className="size-3" /></a> : "—"}
                      {f.source_official && <Badge className="ml-1">official</Badge>}
                      <p className="text-muted-foreground">{formatDate(f.retrieved_at)}</p>
                    </Td>
                    <Td><div className="flex flex-wrap gap-1">
                      {f.status !== "pending" && <StatusBadge status={f.status} />}
                      {f.has_conflict && <Badge variant="destructive"><AlertTriangle />conflict</Badge>}
                      {f.is_duplicate && <Badge variant="secondary"><DupIcon />duplicate</Badge>}
                      <Badge variant="warning">unverified</Badge>
                      <span className="text-[11px] text-muted-foreground tabular-nums">{Math.round(f.confidence * 100)}%</span>
                    </div></Td>
                    <Td className="whitespace-nowrap text-right">{f.status === "pending" && <>
                      <Button size="icon-sm" variant="ghost" onClick={() => review("approve", [f.id])} aria-label="Approve" title="Approve"><Check className="text-success" /></Button>
                      <Button size="icon-sm" variant="ghost" onClick={() => review("reject", [f.id])} aria-label="Reject" title="Reject"><X className="text-destructive" /></Button>
                    </>}</Td>
                  </tr>
                ))}</tbody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
      {tab === "sources" && (
        <Card className="mt-4 p-2">
          <Table>
            <thead><tr><Th>Source</Th><Th>Status</Th><Th>Retrieved</Th></tr></thead>
            <tbody>{job.sources.map((s) => (
              <tr key={s.id}>
                <Td><a href={s.url} target="_blank" rel="noopener noreferrer nofollow" className="font-medium hover:text-primary">{s.title || s.url}</a><p className="text-xs text-muted-foreground break-all">{s.url}</p></Td>
                <Td><div className="flex flex-wrap gap-1">{s.is_official && <Badge><ShieldCheck />official</Badge>}
                  {s.fetch_status === "fetched" ? <Badge variant="success">fetched</Badge> : s.fetch_status === "blocked_robots" ? <Badge variant="destructive"><Ban />robots.txt</Badge> : <Badge variant="secondary">{s.fetch_status.replace("_", " ")}</Badge>}</div></Td>
                <Td className="whitespace-nowrap text-xs text-muted-foreground">{formatDate(s.retrieved_at, true)}</Td>
              </tr>
            ))}</tbody>
          </Table>
        </Card>
      )}
      {tab === "log" && (
        <Card className="mt-4"><CardHeader><CardTitle>Activity log</CardTitle></CardHeader><CardContent>
          <ol className="space-y-1.5 font-mono text-xs">{job.log.map((l, i) => <li key={i}><span className="text-muted-foreground">{formatDate(l.at, true)}</span> — {l.msg}</li>)}</ol>
        </CardContent></Card>
      )}
    </div>
  );
}
