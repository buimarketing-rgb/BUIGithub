import { apiFetch } from "./api";

export type StreamEvent =
  | { type: "meta"; conversation_id: number; conversation_title: string; user_message_id: number }
  | { type: "status"; message: string }
  | { type: "sources"; sources: import("@/types").Source[] }
  | { type: "token"; content: string }
  | { type: "done"; message_id: number; content: string; sources: import("@/types").Source[]; related_questions: string[]; answered: boolean; confidence: number; provider: string; used_web: boolean; latency_ms: number; research_job_id: number | null; created_at: string }
  | { type: "error"; message: string };

export interface ChatRequest { message: string; conversation_id?: number | null; language: string; web?: boolean; regenerate?: boolean; is_voice?: boolean }

/** POSTs a chat request and yields Server-Sent Events as they stream in. */
export async function* streamChat(body: ChatRequest, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
  const res = await apiFetch("/chat/stream", { method: "POST", body: JSON.stringify(body), signal });
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) yield JSON.parse(line.slice(6)) as StreamEvent;
      }
    }
  }
}
