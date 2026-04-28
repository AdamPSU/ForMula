import type { FilterProduct } from "@/lib/api/filter";

// ---------------------------------------------------------------------------
// SSE event vocabulary — mirrors `ai/chat/api.py::_sse` payloads 1:1.
// ---------------------------------------------------------------------------

export type ChatEvent =
  | { type: "thread"; thread_id: string }
  | { type: "messages_delta"; content: string }
  | { type: "message_complete" }
  | {
      type: "tool_call";
      id: string;
      name: ChatToolName;
      arguments: Record<string, unknown>;
    }
  | { type: "phase"; phase: ChatPhase; surfaced_count?: number }
  | { type: "interrupt"; phase: ChatPhase }
  | { type: "final_error"; error: string }
  | { type: "done" };

export type ChatToolName = "explain_product" | "start_quiz";

export type ChatPhase =
  | "init"
  | "awaiting_confirm"
  | "rerank_pending"
  | "relay"
  | "conversing"
  | "ended";

// ---------------------------------------------------------------------------
// Persisted message shape. Mirrors the OpenAI chat schema; tool_calls are
// rendered as inline cards next to the assistant text.
// ---------------------------------------------------------------------------

export type ToolCall = {
  id: string;
  name: ChatToolName;
  arguments: Record<string, unknown>;
};

export type ChatMessage = {
  role: "user" | "assistant" | "tool" | "system";
  content?: string;
  tool_calls?: ToolCall[];
};

// ---------------------------------------------------------------------------
// Resume payloads — sent back to /chat/stream to advance the graph.
// ---------------------------------------------------------------------------

export type ResumePayload =
  | { action: "confirm" }
  | { action: "user_message"; text: string };

// ---------------------------------------------------------------------------
// /chat/state response — used on /results to reattach to an existing thread.
// ---------------------------------------------------------------------------

export type ChatStateResponse = {
  thread_id: string;
  phase: ChatPhase | null;
  messages: ChatMessage[];
  products: FilterProduct[];
  surfaced_count: number;
  reranked: boolean;
  judged: boolean;
  final_error: string | null;
};

// Storage key used to carry thread_id from page 1 to /results.
export const CHAT_THREAD_KEY = "formula:chat-thread";
