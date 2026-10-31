"use client";
import Link from "next/link";
import { Package, FileText, HelpCircle, Users, MessageSquareText, Globe, Clock, TrendingUp, AlertCircle, HeartPulse, BookOpen, ArrowRight, CheckCircle2, AlertTriangle } from "lucide-react";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/components/providers";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorBox, Skeleton, PageHeader } from "@/components/ui/misc";
import { timeAgo, cn } from "@/lib/utils";

interface Dash {
  totals: Record<string, number>;
  recently_updated: { type: string; id: number; title: string; updated_at: string; detail: string }[];
  most_asked: { question: string; count: number; last_asked: string }[];
  unanswered: { question: string; count: number; last_asked: string }[];
  health: { score: number; answer_rate: number; documents_ready: number; documents_failed: number; products_needing_review: number; stale_products: number; pending_research_findings: number; indexed_chunks: number; helpful_rate: number | null };
}

const LINK: Record<string, (id: number) => string> = { product: (id) => `/products/${id}`, document: (id) => `/documents?open=${id}`, faq: () => "/faqs" };
const TYPE_ICON: Record<string, React.ElementType> = { product: Package, document: FileText, faq: HelpCircle };

function Stat({ label, value, icon: Icon, href, sub }: { label: string; value?: number; icon: React.ElementType; href?: string; sub?: string }) {
  const body = (
    <Card className="p-4 transition-colors hover:border-primary/40 h-full">
      <div className="flex items-center justify-between text-muted-foreground"><span className="text-xs font-medium">{label}</span><Icon className="size-4" /></div>
      {value === undefined ? <Skeleton className="mt-2 h-8 w-16" /> : <p className="mt-2 text-3xl font-semibold tabular-nums tracking-tight">{value.toLocaleString()}</p>}
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </Card>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}

export default function DashboardPage() {
  const { user, can } = useAuth();
  const { data, error, reload } = useApi<Dash>("/analytics/dashboard");
  const t = data?.totals;
  const h = data?.health;
  const healthState = !h ? null : h.score >= 80 ? { label: "Healthy", variant: "success" as const, Icon: CheckCircle2 } : h.score >= 60 ? { label: "Needs attention", variant: "warning" as const, Icon: AlertTriangle } : { label: "At risk", variant: "destructive" as const, Icon: AlertCircle };

  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-6">
      <PageHeader title={`Welcome, ${user?.full_name.split(" ")[0]}`} description="An overview of BUI's knowledge and how your team is using it."
        actions={<Link href="/assistant"><Button><MessageSquareText />Ask BUI</Button></Link>} />
      {error && <ErrorBox message={error} onRetry={reload} />}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Total Products" value={t?.products} icon={Package} href="/products" />
        <Stat label="Knowledge Documents" value={t?.documents} icon={FileText} href="/documents" />
        <Stat label="FAQs" value={t?.faqs} icon={HelpCircle} href="/faqs" />
        <Stat label="Team Members" value={t?.team_members} icon={Users} href={can("admin") ? "/team" : undefined} />
        <Stat label="Questions Asked" value={t?.questions} icon={MessageSquareText} sub={t ? `${t.questions_30d} in the last 30 days` : undefined} href={can("admin") ? "/analytics" : undefined} />
        <Stat label="Research Activities" value={t?.research_jobs} icon={Globe} href={can("admin") ? "/research" : undefined} />
        <Stat label="Unanswered Questions" value={t?.unanswered_open} icon={AlertCircle} href={can("admin") ? "/analytics?tab=gaps" : undefined} sub="Open knowledge gaps" />
        <Card className="p-4">
          <div className="flex items-center justify-between text-muted-foreground"><span className="text-xs font-medium">Knowledge Base Health</span><HeartPulse className="size-4" /></div>
          {h && healthState ? (
            <>
              <p className="mt-2 text-3xl font-semibold tabular-nums">{h.score}<span className="text-base text-muted-foreground">/100</span></p>
              <Badge variant={healthState.variant} className="mt-1"><healthState.Icon />{healthState.label}</Badge>
            </>
          ) : <Skeleton className="mt-2 h-8 w-16" />}
        </Card>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle className="flex items-center gap-2"><Clock className="size-4" />Recently Updated Information</CardTitle></CardHeader>
          <CardContent className="space-y-1">
            {!data && [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}
            {data?.recently_updated.length === 0 && <p className="text-sm text-muted-foreground">Nothing yet. Add products or documents to get started.</p>}
            {data?.recently_updated.map((r) => {
              const Icon = TYPE_ICON[r.type] || BookOpen;
              return (
                <Link key={`${r.type}-${r.id}`} href={LINK[r.type]?.(r.id) || "#"} className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-secondary">
                  <Icon className="size-4 text-primary shrink-0" />
                  <span className="min-w-0 flex-1 truncate text-sm">{r.title}</span>
                  <Badge variant="secondary" className="hidden sm:inline-flex capitalize">{r.detail}</Badge>
                  <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(r.updated_at)}</span>
                </Link>
              );
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><HeartPulse className="size-4" />Knowledge Health</CardTitle><CardDescription>What keeps BUI accurate</CardDescription></CardHeader>
          <CardContent>
            {h ? (
              <dl className="space-y-2.5 text-sm">
                {[
                  ["Answer rate (30 days)", `${h.answer_rate}%`],
                  ["Helpful feedback", h.helpful_rate === null ? "—" : `${h.helpful_rate}%`],
                  ["Indexed knowledge chunks", h.indexed_chunks.toLocaleString()],
                  ["Documents processed", h.documents_ready.toLocaleString()],
                  ["Documents failed", h.documents_failed],
                  ["Products needing review", h.products_needing_review],
                  ["Products not updated in 6 months", h.stale_products],
                  ["Research findings awaiting review", h.pending_research_findings],
                ].map(([k, v]) => (
                  <div key={k as string} className="flex justify-between gap-2"><dt className="text-muted-foreground">{k}</dt><dd className={cn("font-medium tabular-nums", typeof v === "number" && v > 0 && /failed|review|6 months/.test(k as string) && "text-warning")}>{v}</dd></div>
                ))}
              </dl>
            ) : <Skeleton className="h-48" />}
            {can("admin") && h && h.pending_research_findings > 0 && <Link href="/research"><Button variant="outline" size="sm" className="mt-4 w-full">Review research findings<ArrowRight /></Button></Link>}
          </CardContent>
        </Card>

        <Card className={cn(!can("admin") && "lg:col-span-3")}>
          <CardHeader><CardTitle className="flex items-center gap-2"><TrendingUp className="size-4" />Most Asked Questions</CardTitle><CardDescription>Last 30 days</CardDescription></CardHeader>
          <CardContent className="space-y-1">
            {data?.most_asked.length === 0 && <p className="text-sm text-muted-foreground">No questions yet.</p>}
            {data?.most_asked.map((q) => (
              <Link key={q.question} href={`/assistant?q=${encodeURIComponent(q.question)}`} className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-secondary">
                <span className="min-w-0 flex-1 truncate text-sm first-letter:uppercase">{q.question}</span>
                <Badge variant="secondary">{q.count}×</Badge>
              </Link>
            ))}
          </CardContent>
        </Card>

        {can("admin") && (
          <Card className="lg:col-span-2">
            <CardHeader className="flex-row items-center justify-between">
              <div><CardTitle className="flex items-center gap-2"><AlertCircle className="size-4" />Unanswered Questions</CardTitle><CardDescription>Questions BUI could not answer from verified knowledge</CardDescription></div>
              <Link href="/analytics?tab=gaps"><Button size="sm" variant="ghost">Manage<ArrowRight /></Button></Link>
            </CardHeader>
            <CardContent className="space-y-1">
              {data?.unanswered.length === 0 && <p className="text-sm text-muted-foreground">No open knowledge gaps. 🎉</p>}
              {data?.unanswered.map((q) => (
                <div key={q.question} className="flex items-center gap-3 rounded-lg px-2 py-2">
                  <span className="min-w-0 flex-1 truncate text-sm first-letter:uppercase">{q.question}</span>
                  <span className="text-xs text-muted-foreground">{timeAgo(q.last_asked)}</span>
                  <Badge variant="warning">{q.count}×</Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
