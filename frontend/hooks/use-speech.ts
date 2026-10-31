"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/services/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Rec = any;

export const VOICE_LANGUAGES = [
  { code: "en-US", label: "English (US)" }, { code: "en-GB", label: "English (UK)" }, { code: "en-IN", label: "English (India)" },
  { code: "hi-IN", label: "हिन्दी (Hindi)" }, { code: "mr-IN", label: "मराठी (Marathi)" }, { code: "gu-IN", label: "ગુજરાતી (Gujarati)" },
  { code: "ta-IN", label: "தமிழ் (Tamil)" }, { code: "te-IN", label: "తెలుగు (Telugu)" }, { code: "kn-IN", label: "ಕನ್ನಡ (Kannada)" },
  { code: "bn-IN", label: "বাংলা (Bengali)" }, { code: "es-ES", label: "Español" }, { code: "fr-FR", label: "Français" },
  { code: "de-DE", label: "Deutsch" }, { code: "pt-BR", label: "Português" }, { code: "ar-SA", label: "العربية" },
  { code: "zh-CN", label: "中文" }, { code: "ja-JP", label: "日本語" },
];

/** Removes a leading wake phrase such as "Hey BUI," from a transcript. */
export function stripWakeWord(text: string) {
  return text.replace(/^\s*(hey|hi|ok|okay)[\s,]+(bui|buy|bee you eye|b u i|bui assistant)[\s,.!:-]*/i, "").trim();
}

/** Converts markdown into plain text suitable for reading aloud. */
export function speakableText(md: string) {
  return md
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/\|?\s*-{3,}\s*(\|\s*-{3,}\s*)*\|?/g, " ")
    .replace(/\|/g, ", ")
    .replace(/\[(\d+)\]/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[*_#>`~]/g, "")
    .replace(/^\s*[-•]\s+/gm, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

export function useSpeechRecognition(opts: { serverFallback: boolean }) {
  const [supported, setSupported] = useState<boolean>(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [permission, setPermission] = useState<"granted" | "denied" | "prompt" | "unknown">("unknown");
  const recRef = useRef<Rec>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);

  useEffect(() => {
    const w = window as any;
    setSupported(!!(w.SpeechRecognition || w.webkitSpeechRecognition) || (opts.serverFallback && !!w.MediaRecorder));
    navigator.permissions?.query({ name: "microphone" as PermissionName }).then((p) => {
      setPermission(p.state as any);
      p.onchange = () => setPermission(p.state as any);
    }).catch(() => setPermission("unknown"));
  }, [opts.serverFallback]);

  const stop = useCallback(() => {
    recRef.current?.stop?.();
    if (mediaRef.current && mediaRef.current.state !== "inactive") mediaRef.current.stop();
  }, []);

  const start = useCallback((lang: string, onFinal: (text: string) => void) => {
    setError(null);
    setInterim("");
    const w = window as any;
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (Ctor) {
      const rec: Rec = new Ctor();
      rec.lang = lang;
      rec.interimResults = true;
      rec.continuous = false;
      rec.maxAlternatives = 1;
      let finalText = "";
      rec.onresult = (e: any) => {
        let txt = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          if (e.results[i].isFinal) finalText += e.results[i][0].transcript;
          else txt += e.results[i][0].transcript;
        }
        setInterim(finalText + txt);
      };
      rec.onerror = (e: any) => {
        const map: Record<string, string> = {
          "not-allowed": "Microphone access was blocked. Allow microphone permission in your browser's site settings.",
          "service-not-allowed": "Speech recognition is not allowed in this browser context (HTTPS is required).",
          "no-speech": "I didn't hear anything. Tap the microphone and try again.",
          "audio-capture": "No microphone was found.",
          network: "Speech recognition needs a network connection in this browser.",
        };
        if (e.error !== "aborted") setError(map[e.error] || `Speech recognition error: ${e.error}`);
        if (e.error === "not-allowed") setPermission("denied");
      };
      rec.onend = () => {
        setListening(false);
        const text = stripWakeWord(finalText);
        setInterim("");
        if (text) onFinal(text);
      };
      recRef.current = rec;
      try { rec.start(); setListening(true); } catch (err) { setError((err as Error).message); }
      return;
    }
    if (!opts.serverFallback) {
      setError("Voice input isn't supported in this browser. Try Chrome, Edge or Safari.");
      return;
    }
    // Fallback: record audio and transcribe with server-side Whisper
    navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      setPermission("granted");
      const rec = new MediaRecorder(stream);
      const parts: Blob[] = [];
      rec.ondataavailable = (e) => parts.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setListening(false);
        setInterim("Transcribing…");
        try {
          const fd = new FormData();
          fd.append("file", new Blob(parts, { type: rec.mimeType || "audio/webm" }), "speech.webm");
          fd.append("language", lang);
          const res = await apiFetch("/voice/transcribe", { method: "POST", body: fd });
          const { text } = await res.json();
          const clean = stripWakeWord(text || "");
          if (clean) onFinal(clean); else setError("I couldn't make out any words. Please try again.");
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setInterim("");
        }
      };
      mediaRef.current = rec;
      rec.start();
      setListening(true);
      setTimeout(() => rec.state !== "inactive" && rec.stop(), 15000);
    }).catch(() => {
      setPermission("denied");
      setError("Microphone access was blocked. Allow microphone permission in your browser's site settings.");
    });
  }, [opts.serverFallback]);

  return { supported, listening, interim, error, permission, start, stop, setError };
}

export function useSpeechSynthesis() {
  const [supported, setSupported] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const lastRef = useRef<{ text: string; lang: string } | null>(null);

  useEffect(() => {
    setSupported("speechSynthesis" in window);
    // Some browsers load voices asynchronously
    window.speechSynthesis?.getVoices();
    return () => window.speechSynthesis?.cancel();
  }, []);

  const speak = useCallback((markdown: string, lang: string, onEnd?: () => void) => {
    if (!("speechSynthesis" in window)) return;
    const text = speakableText(markdown);
    if (!text) return;
    lastRef.current = { text: markdown, lang };
    window.speechSynthesis.cancel();
    const voices = window.speechSynthesis.getVoices();
    const voice = voices.find((v) => v.lang === lang) || voices.find((v) => v.lang.startsWith(lang.split("-")[0]));
    // Chrome stops long utterances after ~15s, so speak sentence groups sequentially
    const parts = text.match(/[^.!?]+[.!?]*\s*/g)?.reduce<string[]>((acc, s) => {
      if (acc.length && (acc[acc.length - 1] + s).length < 220) acc[acc.length - 1] += s; else acc.push(s);
      return acc;
    }, []) || [text];
    setSpeaking(true);
    parts.forEach((p, i) => {
      const u = new SpeechSynthesisUtterance(p);
      u.lang = lang;
      if (voice) u.voice = voice;
      u.rate = 1.02;
      if (i === parts.length - 1) {
        u.onend = () => { setSpeaking(false); onEnd?.(); };
        u.onerror = () => setSpeaking(false);
      }
      window.speechSynthesis.speak(u);
    });
  }, []);

  const stop = useCallback(() => { window.speechSynthesis?.cancel(); setSpeaking(false); }, []);
  const repeat = useCallback(() => { if (lastRef.current) speak(lastRef.current.text, lastRef.current.lang); }, [speak]);

  return { supported, speaking, speak, stop, repeat, hasLast: () => !!lastRef.current };
}
