"use client";
import * as React from "react";
import Link from "next/link";
import { Mic, Square, Repeat, Volume2, VolumeX, MicOff, Loader2, Radio, MessageSquareText, AlertTriangle } from "lucide-react";
import { useAuth } from "@/components/providers";
import { useChat } from "@/hooks/use-chat";
import { usePublicSettings } from "@/hooks/use-public-settings";
import { useSpeechRecognition, useSpeechSynthesis, VOICE_LANGUAGES } from "@/hooks/use-speech";
import { MessageBubble } from "@/components/chat/message";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Phase = "idle" | "listening" | "thinking" | "speaking";

export default function VoicePage() {
  const { user } = useAuth();
  const settings = usePublicSettings();
  const [language, setLanguage] = React.useState(user?.preferred_language || "en-US");
  const [autoSpeak, setAutoSpeak] = React.useState(true);
  const [conversationMode, setConversationMode] = React.useState(false);
  const rec = useSpeechRecognition({ serverFallback: !!settings?.whisper_enabled });
  const tts = useSpeechSynthesis();
  const listenRef = React.useRef<() => void>(() => {});
  const chat = useChat({
    language, isVoice: true,
    onAnswer: (m) => {
      if (autoSpeak && tts.supported) tts.speak(m.content, language, () => { if (conversationMode) setTimeout(() => listenRef.current(), 400); });
      else if (conversationMode) setTimeout(() => listenRef.current(), 400);
    },
  });
  const bottom = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [chat.messages]);

  const listen = React.useCallback(() => {
    tts.stop();
    rec.start(language, (text) => chat.send(text));
  }, [rec, language, chat, tts]);
  listenRef.current = listen;

  const phase: Phase = rec.listening ? "listening" : chat.busy ? "thinking" : tts.speaking ? "speaking" : "idle";
  const lastAnswer = [...chat.messages].reverse().find((m) => m.role === "assistant" && !m.pending);
  const phaseText = {
    idle: rec.supported ? "Tap the microphone and ask a question — e.g. “Hey BUI, what is the warranty of AquaFlow 500?”" : "",
    listening: rec.interim || "Listening…",
    thinking: "Searching the knowledge base…",
    speaking: "Speaking…",
  }[phase];

  return (
    <div className="mx-auto flex h-full max-w-4xl flex-col px-4 py-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Voice Assistant</h1>
          <p className="text-sm text-muted-foreground">Speak naturally. BUI listens, searches company knowledge and reads the answer aloud.</p>
        </div>
        <select value={language} onChange={(e) => setLanguage(e.target.value)} aria-label="Voice language" className="h-9 rounded-md border bg-card px-3 text-sm">
          {VOICE_LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
        </select>
      </div>

      {!rec.supported && (
        <div className="mt-4 flex gap-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
          <AlertTriangle className="size-5 shrink-0 text-warning" />
          <p>Voice input isn&apos;t supported in this browser. Use Chrome, Edge or Safari (desktop or mobile){settings?.whisper_enabled ? "" : ", or ask an administrator to enable server speech recognition (Whisper)"}. You can still type in the <Link className="text-primary underline" href="/assistant">AI Assistant</Link>.</p>
        </div>
      )}
      {rec.permission === "denied" && (
        <div className="mt-4 flex gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm">
          <MicOff className="size-5 shrink-0 text-destructive" />
          <p>Microphone access is blocked. Click the lock icon in your browser&apos;s address bar, allow the microphone for this site, then reload.</p>
        </div>
      )}

      <Card className="mt-6 flex flex-col items-center px-4 py-10 text-center">
        <div className="relative grid place-items-center">
          {phase === "listening" && <span className="absolute size-36 rounded-full bg-brandred/30 animate-pulse-ring" />}
          {phase === "speaking" && <span className="absolute size-36 rounded-full bg-primary/25 animate-pulse-ring" />}
          <button onClick={() => (rec.listening ? rec.stop() : listen())} disabled={!rec.supported || chat.busy}
            aria-label={rec.listening ? "Stop listening" : "Start listening"}
            className={cn("relative grid size-28 place-items-center rounded-full text-white shadow-xl transition-all disabled:opacity-50",
              phase === "listening" ? "bg-brandred scale-105" : "bg-gradient-to-br from-primary to-[#163f73] hover:scale-105")}>
            {phase === "thinking" ? <Loader2 className="size-10 animate-spin" /> : phase === "listening" ? <Square className="size-9" /> : <Mic className="size-11" />}
          </button>
        </div>
        <p className={cn("mt-6 min-h-[3rem] max-w-xl text-sm", phase === "listening" ? "text-foreground font-medium" : "text-muted-foreground")} aria-live="polite">{phaseText}</p>
        {rec.error && <p role="alert" className="mt-1 text-sm text-destructive">{rec.error}</p>}

        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <Button variant="outline" onClick={tts.stop} disabled={!tts.speaking}><VolumeX />Stop speaking</Button>
          <Button variant="outline" onClick={() => lastAnswer && tts.speak(lastAnswer.content, language)} disabled={!lastAnswer || !tts.supported}><Repeat />Repeat answer</Button>
        </div>
        <div className="mt-6 flex flex-wrap justify-center gap-6 text-sm">
          <label className="flex items-center gap-2"><Switch checked={autoSpeak} onChange={setAutoSpeak} label="Read answers aloud" /> <Volume2 className="size-4" />Read answers aloud</label>
          <label className="flex items-center gap-2"><Switch checked={conversationMode} onChange={setConversationMode} label="Conversation mode" /> <Radio className="size-4" />Conversation mode</label>
        </div>
        {conversationMode && <p className="mt-2 text-xs text-muted-foreground">BUI automatically listens again after each answer. Stay silent or tap the button to end.</p>}
        {!tts.supported && <p className="mt-2 text-xs text-muted-foreground">Text-to-speech isn&apos;t available in this browser; answers are shown as text.</p>}
      </Card>

      <div className="mt-6 flex-1 space-y-5">
        {chat.messages.map((m, i) => (
          <MessageBubble key={m.id} m={m} isLast={i === chat.messages.length - 1} onRegenerate={chat.regenerate} onFeedback={chat.feedback}
            onAsk={(q) => chat.send(q)} onResearch={chat.researchOnline} canResearch={false}
            onSpeak={tts.supported ? (t) => tts.speak(t, language) : undefined} speaking={tts.speaking} onStopSpeaking={tts.stop} />
        ))}
        {chat.conversationId && (
          <p className="text-center text-xs text-muted-foreground"><Link href={`/assistant?c=${chat.conversationId}`} className="inline-flex items-center gap-1 text-primary hover:underline"><MessageSquareText className="size-3" />Open this conversation in the AI Assistant</Link></p>
        )}
        {chat.error && <p className="text-sm text-destructive">{chat.error}</p>}
        <div ref={bottom} />
      </div>
    </div>
  );
}
