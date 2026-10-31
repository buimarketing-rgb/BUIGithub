"use client";
import * as React from "react";
import Link from "next/link";
import { Copy, Check, RefreshCw, ThumbsUp, ThumbsDown, Volume2, Square, Globe, ShieldCheck, ExternalLink, ChevronDown, AlertTriangle, BookOpen, Package, HelpCircle, Search } from "lucide-react";
import type { ChatMessage, Source } from "@/types";
import { Markdown } from "./markdown";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/layout/logo";

const SRC_ICON: Record<string, React.ElementType> = { product: Package, document: BookOpen, faq: HelpCircle, research: Globe, web: Globe };

function sourceHref(s: Source) {
  if (s.source_type === "web") return s.url || "#";
  if (s.source_type === "product") return `/products/${s.source_id}`;
  if (s.source_type === "document") return `/documents?open=${s.source_id}`;
  if (s.source_type === "faq") return `/faqs`;
  return s.url || (s.product_id ? `/products/${s.product_id}` : "#");
}

function Sources({ sources, highlight }: { sources: Source[]; highlight: number | null }) {
  const [open, setOpen] = React.useState(true);
  if (!sources.length) return null;
  return (
    <div className="mt-3 rounded-lg border bg-background/60">
      <button className="flex w-full items-center gap-2 px-3 py-2 text-xs font-medium text-muted-foreground" onClick={() => setOpen(!open)}>
        <BookOpen className="size-3.5" /> {sources.length} source{sources.length > 1 ? "s" : ""}
        <ChevronDown className={cn("ml-auto size-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <ol className="space-y-1 px-2 pb-2">
          {sources.map((s) => {
            const Icon = SRC_ICON[s.source_type] || BookOpen;
            const external = s.source_type === "web";
            return (
              <li key={s.n} id={`src-${s.n}`}>
                <Link href={sourceHref(s)} target={external ? "_blank" : undefined} rel={external ? "noopener noreferrer" : undefined}
                  className={cn("flex items-start gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-secondary transition-colors", highlight === s.n && "bg-accent ring-1 ring-primary/40")}>
                  <span className="mt-0.5 grid size-4 shrink-0 place-items-center rounded bg-muted text-[10px] font-semibold">{s.n}</span>
                  <Icon className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">{s.title}</span>{s.section && <span className="text-muted-foreground"> · {s.section}</span>}
                    <span className="flex flex-wrap gap-1.5 mt-1">
                      {s.verified ? <Badge variant="success"><ShieldCheck />Verified</Badge> : <Badge variant="warning"><AlertTriangle />{s.source_type === "web" ? "Unverified web" : "Third-party research"}</Badge>}
                      {s.official && <Badge>Official site</Badge>}
                      {s.updated_at && <span className="text-muted-foreground">{s.source_type === "web" ? "Retrieved" : "Updated"} {s.updated_at}</span>}
                      {s.version && s.source_type !== "web" && <span className="text-muted-foreground">v{s.version}</span>}
                    </span>
                  </span>
                  {external && <ExternalLink className="size-3 shrink-0 text-muted-foreground" />}
                </Link>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

export function MessageBubble({ m, isLast, onRegenerate, onFeedback, onAsk, onResearch, onSpeak, speaking, onStopSpeaking, canResearch, question }: {
  m: ChatMessage; isLast: boolean; onRegenerate: () => void; onFeedback: (id: number, helpful: boolean) => void; onAsk: (q: string) => void;
  onResearch: (q: string) => void; onSpeak?: (text: string) => void; speaking?: boolean; onStopSpeaking?: () => void; canResearch: boolean; question?: string;
}) {
  const [copied, setCopied] = React.useState(false);
  const [cite, setCite] = React.useState<number | null>(null);
  if (m.role === "user") {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-primary-foreground whitespace-pre-wrap shadow-sm">{m.content}</div>
      </div>
    );
  }
  const copy = async () => { await navigator.clipboard.writeText(m.content); setCopied(true); setTimeout(() => setCopied(false), 1500); };
  const onCite = (n: number) => { setCite(n); document.getElementById(`src-${n}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" }); };
  const notFound = m.answered === false && !m.used_web;
  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="hidden sm:block shrink-0 pt-1"><Logo withText={false} className="[&_img]:size-8" /></div>
      <div className="min-w-0 flex-1">
        <div className={cn("rounded-2xl rounded-tl-md border bg-card px-4 py-3 shadow-sm", m.used_web && "border-warning/40")}>
          {m.used_web && !m.pending && (
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-warning"><Globe className="size-3.5" />Online research · not company-verified</div>
          )}
          {m.pending && !m.content ? (
            <div className="flex items-center gap-2 py-1 text-sm text-muted-foreground">
              <span className="flex gap-1">{[0, 1, 2].map((i) => <span key={i} className="size-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />)}</span>
              {m.status}
            </div>
          ) : (
            <Markdown content={m.content} sources={m.sources} onCite={onCite} />
          )}
          {m.pending && m.content && <span className="inline-block h-4 w-1.5 animate-pulse bg-primary align-middle" />}
          <Sources sources={m.sources} highlight={cite} />
          {notFound && canResearch && question && (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => onResearch(question)}><Search />Yes, research it online</Button>
            </div>
          )}
          {m.research_job_id && m.used_web && (
            <p className="mt-2 text-xs text-muted-foreground">Findings were saved for administrator review (research job #{m.research_job_id}).</p>
          )}
        </div>
        {!m.pending && (
          <div className="mt-1.5 flex flex-wrap items-center gap-0.5 text-muted-foreground">
            <Button variant="ghost" size="icon-sm" onClick={copy} title="Copy" aria-label="Copy response">{copied ? <Check /> : <Copy />}</Button>
            {isLast && <Button variant="ghost" size="icon-sm" onClick={onRegenerate} title="Regenerate" aria-label="Regenerate response"><RefreshCw /></Button>}
            {onSpeak && (speaking ? (
              <Button variant="ghost" size="icon-sm" onClick={onStopSpeaking} title="Stop speaking" aria-label="Stop speaking"><Square /></Button>
            ) : (
              <Button variant="ghost" size="icon-sm" onClick={() => onSpeak(m.content)} title="Read aloud" aria-label="Read aloud"><Volume2 /></Button>
            ))}
            {m.id > 0 && <>
              <Button variant="ghost" size="icon-sm" onClick={() => onFeedback(m.id, true)} title="Helpful" aria-label="Helpful" className={cn(m.feedback === true && "text-success")}><ThumbsUp /></Button>
              <Button variant="ghost" size="icon-sm" onClick={() => onFeedback(m.id, false)} title="Not helpful" aria-label="Not helpful" className={cn(m.feedback === false && "text-destructive")}><ThumbsDown /></Button>
            </>}
            {m.provider && <span className="ml-2 text-[11px]">{m.provider}{m.latency_ms ? ` · ${(m.latency_ms / 1000).toFixed(1)}s` : ""}</span>}
          </div>
        )}
        {isLast && !m.pending && m.related_questions.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {m.related_questions.map((q) => (
              <button key={q} onClick={() => onAsk(q)} className="rounded-full border bg-card px-3 py-1.5 text-xs hover:border-primary hover:text-primary transition-colors text-left">{q}</button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
