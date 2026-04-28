import { createClient } from "@/lib/supabase/client";
import type {
  ChatEvent,
  ChatStateResponse,
  ResumePayload,
} from "@/lib/chat/types";

type StreamBody = {
  thread_id?: string;
  user_text?: string;
  personalize?: boolean;
  thinking?: boolean;
  resume?: ResumePayload;
};

/**
 * Open a POST /chat/stream connection and dispatch one parsed event per SSE
 * data line. Resolves when the server emits `{type:"done"}` or closes the
 * stream. Throws on transport errors. The caller owns the AbortSignal so a
 * navigation away or a "stop generating" click cancels the read.
 */
export async function streamChat(
  body: StreamBody,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("not signed in");

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) throw new Error("NEXT_PUBLIC_API_URL is not set");

  const res = await fetch(`${apiUrl}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`/chat/stream ${res.status}: ${text}`);
  }
  if (!res.body) throw new Error("no response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line.
      let split = buffer.indexOf("\n\n");
      while (split !== -1) {
        const frame = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        for (const line of frame.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6);
          if (!raw) continue;
          try {
            const evt = JSON.parse(raw) as ChatEvent;
            onEvent(evt);
            if (evt.type === "done") return;
          } catch {
            // Malformed frame — skip silently.
          }
        }
        split = buffer.indexOf("\n\n");
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Snapshot the current persisted state of a chat thread. Used by /results
 * on initial mount to render whatever the page-1 chat already produced.
 */
export async function getChatState(threadId: string): Promise<ChatStateResponse> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("not signed in");

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) throw new Error("NEXT_PUBLIC_API_URL is not set");

  const res = await fetch(`${apiUrl}/chat/state/${threadId}`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`/chat/state ${res.status}: ${text}`);
  }
  return res.json() as Promise<ChatStateResponse>;
}
