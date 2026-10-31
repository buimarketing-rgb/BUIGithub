"use client";
import { useCallback, useRef, useState } from "react";
import type { ChatMessage } from "@/types";
import { api } from "@/services/api";
import { streamChat } from "@/services/chat-stream";

let tempId = -1;

/** Conversation state + streaming send/regenerate, shared by the text and voice assistants. */
export function useChat(opts: { language: string; isVoice?: boolean; onConversationCreated?: (id: number, title: string) => void; onAnswer?: (m: ChatMessage) => void }) {
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const load = useCallback(async (id: number | null) => {
    abortRef.current?.abort();
    setError(null);
    setConversationId(id);
    if (!id) { setMessages([]); return; }
    try {
      const c = await api<{ messages: ChatMessage[] }>(`/chat/conversations/${id}`);
      setMessages(c.messages);
    } catch (e) { setError((e as Error).message); }
  }, []);

  const run = useCallback(async (text: string, flags: { web?: boolean; regenerate?: boolean } = {}) => {
    if (busy) return;
    setError(null);
    setBusy(true);
    const assistantId = tempId--;
    const placeholder: ChatMessage = {
      id: assistantId, role: "assistant", content: "", sources: [], related_questions: [], answered: null, confidence: null,
      used_web: !!flags.web, provider: null, latency_ms: null, created_at: new Date().toISOString(), feedback: null, pending: true,
      status: flags.web ? "Researching online sources…" : "Searching the knowledge base…",
    };
    setMessages((prev) => {
      let base = prev;
      if (flags.regenerate) { while (base.length && base[base.length - 1].role === "assistant") base = base.slice(0, -1); }
      else base = [...base, { ...placeholder, id: tempId--, role: "user", content: text, pending: false, status: undefined }];
      return [...base, placeholder];
    });
    const update = (fn: (m: ChatMessage) => ChatMessage) => setMessages((prev) => prev.map((m) => (m.id === assistantId ? fn(m) : m)));
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      for await (const ev of streamChat({ message: text, conversation_id: conversationId, language: optsRef.current.language, web: flags.web, regenerate: flags.regenerate, is_voice: optsRef.current.isVoice }, ctrl.signal)) {
        if (ev.type === "meta") {
          if (!conversationId) { setConversationId(ev.conversation_id); optsRef.current.onConversationCreated?.(ev.conversation_id, ev.conversation_title); }
        } else if (ev.type === "status") update((m) => ({ ...m, status: ev.message }));
        else if (ev.type === "sources") update((m) => ({ ...m, sources: ev.sources, status: "Writing answer…" }));
        else if (ev.type === "token") update((m) => ({ ...m, content: m.content + ev.content, status: undefined }));
        else if (ev.type === "done") {
          const final: ChatMessage = {
            id: ev.message_id, role: "assistant", content: ev.content, sources: ev.sources, related_questions: ev.related_questions,
            answered: ev.answered, confidence: ev.confidence, used_web: ev.used_web, provider: ev.provider, latency_ms: ev.latency_ms,
            created_at: ev.created_at, feedback: null, research_job_id: ev.research_job_id,
          };
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? final : m)));
          optsRef.current.onAnswer?.(final);
        } else if (ev.type === "error") { setError(ev.message); update((m) => ({ ...m, pending: false, content: m.content || "_Something went wrong._" })); }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
      setMessages((prev) => prev.filter((m) => !(m.id === assistantId && !m.content)).map((m) => (m.id === assistantId ? { ...m, pending: false } : m)));
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }, [busy, conversationId]);

  const send = useCallback((text: string, web = false) => { const t = text.trim(); if (t) return run(t, { web }); }, [run]);
  const regenerate = useCallback(() => run("", { regenerate: true }), [run]);
  const researchOnline = useCallback((question: string) => run(question, { web: true }), [run]);
  const stop = useCallback(() => abortRef.current?.abort(), []);

  const feedback = useCallback(async (id: number, helpful: boolean) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, feedback: helpful } : m)));
    try { await api(`/chat/messages/${id}/feedback`, { method: "POST", json: { helpful } }); } catch (e) { setError((e as Error).message); }
  }, []);

  return { conversationId, messages, busy, error, setError, load, send, regenerate, researchOnline, stop, feedback };
}
