"use client";
import * as React from "react";
import { ArrowUp, Mic, MicOff, Square, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { VOICE_LANGUAGES, useSpeechRecognition } from "@/hooks/use-speech";

export function Composer({ onSend, onStop, busy, language, setLanguage, canResearch, serverVoice, initial }: {
  onSend: (text: string, web: boolean) => void; onStop: () => void; busy: boolean; language: string; setLanguage: (l: string) => void;
  canResearch: boolean; serverVoice: boolean; initial?: string;
}) {
  const [text, setText] = React.useState(initial || "");
  const [web, setWeb] = React.useState(false);
  const ref = React.useRef<HTMLTextAreaElement>(null);
  const speech = useSpeechRecognition({ serverFallback: serverVoice });

  React.useEffect(() => { if (initial) { setText(initial); ref.current?.focus(); } }, [initial]);
  React.useEffect(() => {
    const el = ref.current;
    if (el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 220) + "px"; }
  }, [text, speech.interim]);

  const submit = () => {
    if (busy || !text.trim()) return;
    onSend(text, web);
    setText("");
    setWeb(false);
  };
  const mic = () => {
    if (speech.listening) { speech.stop(); return; }
    speech.start(language, (spoken) => { onSend(spoken, web); setText(""); });
  };

  return (
    <div className="mx-auto w-full max-w-3xl">
      {speech.error && <p role="alert" className="mb-2 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">{speech.error}</p>}
      <div className={cn("rounded-2xl border bg-card shadow-sm focus-within:ring-2 focus-within:ring-ring transition-shadow", speech.listening && "ring-2 ring-brandred")}>
        <textarea ref={ref} rows={1} value={speech.listening ? speech.interim || "" : text} readOnly={speech.listening}
          onChange={(e) => setText(e.target.value)} maxLength={4000}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); } }}
          placeholder={speech.listening ? "Listening… speak your question" : web ? "Ask BUI to research a product online…" : "Ask BUI about products, specifications, warranty, installation…"}
          aria-label="Message BUI" className="block w-full resize-none bg-transparent px-4 pt-3.5 pb-2 text-sm focus:outline-none placeholder:text-muted-foreground" />
        <div className="flex items-center gap-1.5 px-2.5 pb-2.5">
          <select value={language} onChange={(e) => setLanguage(e.target.value)} aria-label="Language"
            className="h-8 max-w-[130px] rounded-md border-0 bg-secondary px-2 text-xs focus:outline-none">
            {VOICE_LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
          {canResearch && (
            <button type="button" onClick={() => setWeb(!web)} aria-pressed={web} title="Research online (results are marked unverified)"
              className={cn("inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium transition-colors", web ? "bg-warning/15 text-warning" : "text-muted-foreground hover:bg-secondary")}>
              <Globe className="size-3.5" /><span className="hidden sm:inline">Web research</span>
            </button>
          )}
          <div className="ml-auto flex items-center gap-1.5">
            {speech.supported ? (
              <Button type="button" variant={speech.listening ? "destructive" : "ghost"} size="icon" onClick={mic} disabled={busy}
                aria-label={speech.listening ? "Stop listening" : "Speak your question"} title={speech.permission === "denied" ? "Microphone blocked" : "Voice input"}>
                {speech.permission === "denied" ? <MicOff /> : <Mic />}
              </Button>
            ) : null}
            {busy ? (
              <Button size="icon" variant="secondary" onClick={onStop} aria-label="Stop generating"><Square /></Button>
            ) : (
              <Button size="icon" onClick={submit} disabled={!text.trim()} aria-label="Send" className="rounded-full"><ArrowUp /></Button>
            )}
          </div>
        </div>
      </div>
      <p className="mt-2 text-center text-[11px] text-muted-foreground">BUI answers only from approved company knowledge and cites its sources. Online research is always marked unverified.</p>
    </div>
  );
}
