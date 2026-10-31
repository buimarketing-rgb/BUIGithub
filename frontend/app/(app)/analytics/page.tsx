"use client";
import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { BarChart3, MessageSquareText, CheckCircle2, Timer, ThumbsUp, ThumbsDown, Users, Globe, Plus, Check, Search } from "lucide-react";
import { api } from "@/services/api";
import { useApi } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea, Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorBox, PageHeader, Skeleton, Tabs } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { useProductOptions } from "@/components/documents/document-dialogs";
import { QuestionsChart } from "@/components/analytics/questions-chart";
import { timeAgo } from "@/lib/utils";

interface Overview {
  days: number; questions_per_day: { date: string; questions: number; answered: number }[];
  totals: { questions: number; answered: number; answer_rate: number | null; avg_latency_ms: number | null; avg_confidence: number | null; web_answers: number; helpful: number; not_helpful: number; active_users: number };
  top_questions: { question: string; count: number }[]; top_products: { product_id: number; name: string; count: number }[];
  low_confidence: { message_id: number; question: string; confidence: number; created_at: string }[];
}
interface Gap { question: string; count: number; last_asked: string }
interface FeedbackRow { id: number; helpful: boolean; comment: string | null; question: string | null; answer: string; user: string; created_at: string }

function Kpi({ label, value, icon: Icon }: { label: string; value: React.ReactNode; icon: React.ElementType }) {
  return <Card className="p-4"><div className="flex items-center justify-between text-xs text-muted-foreground">{label}<Icon className="size-4" /></div><p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p></Card>;
}

function OverviewTab() {
  const [days, setDays] = React.useState(30);
  const { data, error, reload } = useApi<Overview>(`/analytics/overview?days=${days}`);
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return <Skeleton className="h-96" />;
  const t = data.totals;
  return (
    <div className="space-y-4">
      <div className="flex justify-end"><Select className="w-40" value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Period"><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option></Select></div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Kpi label="Questions" value={t.questions} icon={MessageSquareText} />
        <Kpi label="Answer rate" value={t.answer_rate === null ? "—" : `${t.answer_rate}%`} icon={CheckCircle2} />
        <Kpi label="Avg. response" value={t.avg_latency_ms ? `${(t.avg_latency_ms / 1000).toFixed(1)}s` : "—"} icon={Timer} />
        <Kpi label="Helpful / not" value={<span>{t.helpful} <span className="text-muted-foreground">/</span> {t.not_helpful}</span>} icon={ThumbsUp} />
        <Kpi label="Active users" value={t.active_users} icon={Users} />
        <Kpi label="Web research answers" value={t.web_answers} icon={Globe} />
      </div>
      <Card><CardHeader><CardTitle>Questions per day</CardTitle></CardHeader><CardContent><QuestionsChart data={data.questions_per_day} days={days} /></CardContent></Card>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card><CardHeader><CardTitle>Most frequent questions</CardTitle></CardHeader><CardContent className="space-y-1.5">
          {data.top_questions.length === 0 && <p className="text-sm text-muted-foreground">No data yet.</p>}
          {data.top_questions.map((q) => <div key={q.question} className="flex gap-2 text-sm"><span className="flex-1 truncate first-letter:uppercase">{q.question}</span><Badge variant="secondary">{q.count}</Badge></div>)}
        </CardContent></Card>
        <Card><CardHeader><CardTitle>Most searched products</CardTitle></CardHeader><CardContent className="space-y-1.5">
          {data.top_products.length === 0 && <p className="text-sm text-muted-foreground">No data yet.</p>}
          {data.top_products.map((p) => <Link key={p.product_id} href={`/products/${p.product_id}`} className="flex gap-2 text-sm hover:text-primary"><span className="flex-1 truncate">{p.name}</span><Badge variant="secondary">{p.count}</Badge></Link>)}
        </CardContent></Card>
        <Card><CardHeader><CardTitle>Low-confidence answers</CardTitle><CardDescription>Answered, but with weak retrieval matches</CardDescription></CardHeader><CardContent className="space-y-1.5">
          {data.low_confidence.length === 0 && <p className="text-sm text-muted-foreground">None. 👍</p>}
          {data.low_confidence.map((l) => <div key={l.message_id} className="flex gap-2 text-sm"><span className="flex-1 truncate">{l.question}</span><Badge variant="warning">{Math.round(l.confidence * 100)}%</Badge></div>)}
        </CardContent></Card>
      </div>
    </div>
  );
}

function GapsTab() {
  const toast = useToast();
  const products = useProductOptions();
  const [resolved, setResolved] = React.useState(false);
  const { data, error, reload } = useApi<Gap[]>(`/analytics/unanswered?include_resolved=${resolved}`);
  const [faq, setFaq] = React.useState<{ question: string; answer: string; product_id: string } | null>(null);
  const [busy, setBusy] = React.useState(false);
  const resolve = async (question: string) => { await api("/analytics/unanswered/resolve", { method: "POST", json: { question } }); toast.success("Marked as resolved"); reload(); };
  const createFaq = async () => {
    if (!faq) return;
    setBusy(true);
    try { await api("/analytics/unanswered/to-faq", { method: "POST", json: { question: faq.question, answer: faq.answer, product_id: faq.product_id ? Number(faq.product_id) : null } }); toast.success("FAQ created", "BUI can now answer this question."); setFaq(null); reload(); }
    catch (e) { toast.error((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2">
        <div><CardTitle>Questions BUI could not answer</CardTitle><CardDescription>Turn knowledge gaps into FAQs, or add documents and products, then mark them resolved.</CardDescription></div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={resolved} onChange={(e) => setResolved(e.target.checked)} />Include resolved</label>
      </CardHeader>
      <CardContent>
        {error && <ErrorBox message={error} onRetry={reload} />}
        {data?.length === 0 && <EmptyState icon={CheckCircle2} title="No knowledge gaps" description="Every recent question was answered from verified knowledge." />}
        <div className="divide-y">
          {data?.map((g) => (
            <div key={g.question} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1"><p className="text-sm font-medium first-letter:uppercase">{g.question}</p><p className="text-xs text-muted-foreground">Asked {g.count}× · last {timeAgo(g.last_asked)}</p></div>
              <div className="flex flex-wrap gap-1.5">
                <Button size="sm" onClick={() => setFaq({ question: g.question.charAt(0).toUpperCase() + g.question.slice(1), answer: "", product_id: "" })}><Plus />Create FAQ</Button>
                <Link href={`/research?q=${encodeURIComponent(g.question)}`}><Button size="sm" variant="outline"><Search />Research</Button></Link>
                <Button size="sm" variant="ghost" onClick={() => resolve(g.question)}><Check />Resolve</Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
      <Dialog open={!!faq} onClose={() => setFaq(null)} title="Create FAQ from question" description="The answer becomes verified company knowledge immediately."
        footer={<><Button variant="outline" onClick={() => setFaq(null)}>Cancel</Button><Button onClick={createFaq} loading={busy} disabled={!faq?.answer.trim()}>Create FAQ</Button></>}>
        {faq && <div className="grid gap-4">
          <Field label="Question"><Input value={faq.question} onChange={(e) => setFaq({ ...faq, question: e.target.value })} /></Field>
          <Field label="Approved answer"><Textarea rows={6} value={faq.answer} onChange={(e) => setFaq({ ...faq, answer: e.target.value })} /></Field>
          <Field label="Product"><Select value={faq.product_id} onChange={(e) => setFaq({ ...faq, product_id: e.target.value })}><option value="">General</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
        </div>}
      </Dialog>
    </Card>
  );
}

function FeedbackTab() {
  const { data } = useApi<FeedbackRow[]>("/analytics/feedback");
  if (!data) return <Skeleton className="h-64" />;
  return (
    <Card><CardHeader><CardTitle>Recent answer feedback</CardTitle></CardHeader><CardContent>
      {data.length === 0 && <EmptyState icon={ThumbsUp} title="No feedback yet" />}
      <div className="divide-y">{data.map((f) => (
        <div key={f.id} className="flex gap-3 py-3">
          {f.helpful ? <ThumbsUp className="size-4 shrink-0 text-success" /> : <ThumbsDown className="size-4 shrink-0 text-destructive" />}
          <div className="min-w-0 flex-1 text-sm">
            <p className="font-medium">{f.question}</p>
            <p className="line-clamp-2 text-xs text-muted-foreground">{f.answer}</p>
            {f.comment && <p className="mt-1 text-xs">“{f.comment}”</p>}
          </div>
          <span className="shrink-0 text-xs text-muted-foreground">{f.user}<br />{timeAgo(f.created_at)}</span>
        </div>
      ))}</div>
    </CardContent></Card>
  );
}

function AnalyticsInner() {
  const params = useSearchParams();
  const [tab, setTab] = React.useState<"overview" | "gaps" | "feedback">((params.get("tab") as "gaps") || "overview");
  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-6">
      <PageHeader icon={BarChart3} title="Analytics" description="How your team uses BUI, and where its knowledge needs improving." />
      <Tabs className="mb-4" value={tab} onChange={setTab} tabs={[{ value: "overview", label: "Overview" }, { value: "gaps", label: "Knowledge gaps" }, { value: "feedback", label: "Feedback" }]} />
      {tab === "overview" && <OverviewTab />}
      {tab === "gaps" && <GapsTab />}
      {tab === "feedback" && <FeedbackTab />}
    </div>
  );
}
export default function AnalyticsPage() { return <React.Suspense><AnalyticsInner /></React.Suspense>; }
