"use client";
import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { History, List, GitCompare, Sparkles, Wrench, ShieldCheck, Globe, X } from "lucide-react";
import { useAuth } from "@/components/providers";
import { useChat } from "@/hooks/use-chat";
import { useApi } from "@/hooks/use-api";
import { usePublicSettings } from "@/hooks/use-public-settings";
import { useSpeechSynthesis } from "@/hooks/use-speech";
import { ChatHistory } from "@/components/chat/history";
import { Composer } from "@/components/chat/composer";
import { MessageBubble } from "@/components/chat/message";
import { ErrorBox } from "@/components/ui/misc";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const ICONS: Record<string, React.ElementType> = { list: List, "git-compare": GitCompare, sparkles: Sparkles, wrench: Wrench, "shield-check": ShieldCheck, globe: Globe };
interface Suggestion { icon: string; title: string; prompt: string; web?: boolean }

function AssistantInner() {
  const { user, can } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const settings = usePublicSettings();
  const [language, setLanguage] = React.useState(user?.preferred_language || "en-US");
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [historyOpen, setHistoryOpen] = React.useState(false);
  const [draft, setDraft] = React.useState<string | undefined>(undefined);
  const tts = useSpeechSynthesis();
  const chat = useChat({ language, onConversationCreated: (id) => { setRefreshKey((k) => k + 1); router.replace(`/assistant?c=${id}`, { scroll: false }); } });
  const { data: suggestions } = useApi<Suggestion[]>("/chat/suggestions");
  const bottom = React.useRef<HTMLDivElement>(null);
  const canResearch = !!settings?.web_research_enabled && (can("admin") || !!settings?.team_can_research_from_chat);

  const cParam = params.get("c");
  React.useEffect(() => {
    const id = cParam ? Number(cParam) : null;
    if (id !== chat.conversationId) chat.load(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cParam]);
  React.useEffect(() => {
    const q = params.get("q");
    if (q) { router.replace("/assistant"); chat.send(q); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  React.useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [chat.messages]);

  const select = (id: number) => { setHistoryOpen(false); router.push(`/assistant?c=${id}`); };
  const newChat = () => { setHistoryOpen(false); tts.stop(); router.push("/assistant"); chat.load(null); };
  const lastUserQuestion = (idx: number) => [...chat.messages.slice(0, idx)].reverse().find((m) => m.role === "user")?.content;

  return (
    <div className="flex h-full">
      <aside className={cn("w-72 shrink-0 border-r bg-card/50", "hidden md:block")}>
        <ChatHistory activeId={chat.conversationId} onSelect={select} onNew={newChat} refreshKey={refreshKey} />
      </aside>
      {historyOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setHistoryOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-80 max-w-[85%] bg-card shadow-xl">
            <div className="flex justify-end p-2"><Button size="icon-sm" variant="ghost" onClick={() => setHistoryOpen(false)} aria-label="Close history"><X /></Button></div>
            <ChatHistory activeId={chat.conversationId} onSelect={select} onNew={newChat} refreshKey={refreshKey} />
          </div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b px-3 py-2 md:hidden">
          <Button variant="ghost" size="sm" onClick={() => setHistoryOpen(true)}><History />History</Button>
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-thin px-3 sm:px-6">
          {chat.messages.length === 0 ? (
            <div className="mx-auto flex min-h-full max-w-3xl flex-col items-center justify-center py-10 text-center">
              <div className="relative mb-6">
                <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-brandred/40 to-primary/40 blur-2xl" />
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/bui-logo.jpg" alt="" className="relative size-20 rounded-3xl shadow-lg ring-1 ring-border" />
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">BUI – How can I help you today?</h1>
              <p className="mt-2 text-sm text-muted-foreground max-w-lg">Ask about {settings?.company_name || "your company"}&apos;s products, specifications, warranties, installation and policies. Every answer cites its source.</p>
              <div className="mt-8 grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {(suggestions || []).filter((s) => !s.web || canResearch).map((s) => {
                  const Icon = ICONS[s.icon] || Sparkles;
                  return (
                    <button key={s.title} onClick={() => (s.web ? setDraft(s.prompt) : chat.send(s.prompt))}
                      className="group rounded-xl border bg-card p-4 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-md">
                      <Icon className="size-5 text-primary" />
                      <p className="mt-3 text-sm font-medium">{s.title}</p>
                      <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{s.web ? "Search the web; findings are marked unverified" : s.prompt}</p>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-6 py-6">
              {chat.messages.map((m, i) => (
                <MessageBubble key={m.id} m={m} isLast={i === chat.messages.length - 1} question={lastUserQuestion(i)}
                  onRegenerate={chat.regenerate} onFeedback={chat.feedback} onAsk={(q) => chat.send(q)} onResearch={chat.researchOnline} canResearch={canResearch}
                  onSpeak={tts.supported ? (t) => tts.speak(t, language) : undefined} speaking={tts.speaking} onStopSpeaking={tts.stop} />
              ))}
              <div ref={bottom} />
            </div>
          )}
        </div>
        <div className="border-t bg-background/80 px-3 py-3 backdrop-blur sm:px-6">
          {chat.error && <div className="mx-auto mb-2 max-w-3xl"><ErrorBox message={chat.error} onRetry={() => chat.setError(null)} /></div>}
          <Composer onSend={(t, web) => chat.send(t, web)} onStop={chat.stop} busy={chat.busy} language={language} setLanguage={setLanguage}
            canResearch={canResearch} serverVoice={!!settings?.whisper_enabled} initial={draft} />
        </div>
      </div>
    </div>
  );
}

export default function AssistantPage() {
  return <React.Suspense><AssistantInner /></React.Suspense>;
}
