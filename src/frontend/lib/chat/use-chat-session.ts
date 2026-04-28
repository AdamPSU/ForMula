"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";

import { getChatState, streamChat } from "@/lib/api/chat";
import type {
  ChatEvent,
  ChatMessage,
  ChatPhase,
  ChatStateResponse,
  ResumePayload,
} from "@/lib/chat/types";

type SessionState = {
  threadId: string | null;
  messages: ChatMessage[];
  phase: ChatPhase | null;
  /** Filter's surfaced count, set when the awaiting_confirm phase fires. */
  surfacedCount: number | null;
  /** True while an SSE stream is open. */
  isStreaming: boolean;
  /** True after a stream's final `interrupt` (graph paused, awaiting user). */
  isWaiting: boolean;
  /** True once the graph has reached an `__end__` or final_error. */
  isEnded: boolean;
  error: string | null;
};

const INITIAL: SessionState = {
  threadId: null,
  messages: [],
  phase: null,
  surfacedCount: null,
  isStreaming: false,
  isWaiting: false,
  isEnded: false,
  error: null,
};

type Action =
  | { type: "STREAM_START" }
  | { type: "STREAM_END" }
  | { type: "RESET" }
  | { type: "SET_THREAD"; thread_id: string }
  | { type: "SET_PHASE"; phase: ChatPhase; surfaced_count?: number }
  | { type: "DELTA"; content: string }
  | { type: "INTERRUPT" }
  | { type: "ERROR"; error: string }
  | { type: "ADD_USER"; text: string }
  | { type: "REPLACE_FROM_STATE"; snapshot: ChatStateResponse };

function reducer(s: SessionState, a: Action): SessionState {
  switch (a.type) {
    case "STREAM_START":
      return { ...s, isStreaming: true, isWaiting: false, error: null };
    case "STREAM_END":
      return { ...s, isStreaming: false };
    case "RESET":
      return INITIAL;
    case "SET_THREAD":
      return { ...s, threadId: a.thread_id };
    case "SET_PHASE":
      return {
        ...s,
        phase: a.phase,
        surfacedCount:
          a.surfaced_count !== undefined ? a.surfaced_count : s.surfacedCount,
        isEnded: a.phase === "ended",
      };
    case "DELTA": {
      const last = s.messages[s.messages.length - 1];
      if (last && last.role === "assistant") {
        const updated: ChatMessage = {
          ...last,
          content: (last.content ?? "") + a.content,
        };
        return {
          ...s,
          messages: [...s.messages.slice(0, -1), updated],
        };
      }
      return {
        ...s,
        messages: [...s.messages, { role: "assistant", content: a.content }],
      };
    }
    case "INTERRUPT":
      return { ...s, isWaiting: true };
    case "ERROR":
      return { ...s, error: a.error, isStreaming: false };
    case "ADD_USER":
      return {
        ...s,
        messages: [...s.messages, { role: "user", content: a.text }],
      };
    case "REPLACE_FROM_STATE":
      return {
        ...s,
        threadId: a.snapshot.thread_id,
        messages: a.snapshot.messages,
        phase: a.snapshot.phase,
        isWaiting:
          a.snapshot.phase === "relay" || a.snapshot.phase === "conversing",
        isEnded:
          a.snapshot.phase === "ended" || Boolean(a.snapshot.final_error),
        error: a.snapshot.final_error,
      };
    default:
      return s;
  }
}

export function useChatSession() {
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const abortRef = useRef<AbortController | null>(null);
  const threadIdRef = useRef<string | null>(null);

  // Mirror threadId into a ref so callbacks can read the current value
  // without re-binding when state updates.
  useEffect(() => {
    threadIdRef.current = state.threadId;
  }, [state.threadId]);

  // Cancel any in-flight stream on unmount.
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const runStream = useCallback(
    async (body: {
      thread_id?: string;
      user_text?: string;
      personalize?: boolean;
      thinking?: boolean;
      resume?: ResumePayload;
    }) => {
      // Abort any prior stream before starting a new one.
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;

      dispatch({ type: "STREAM_START" });
      try {
        await streamChat(
          body,
          (evt: ChatEvent) => {
            switch (evt.type) {
              case "thread":
                threadIdRef.current = evt.thread_id;
                dispatch({ type: "SET_THREAD", thread_id: evt.thread_id });
                return;
              case "phase":
                dispatch({
                  type: "SET_PHASE",
                  phase: evt.phase,
                  surfaced_count: evt.surfaced_count,
                });
                return;
              case "messages_delta":
                dispatch({ type: "DELTA", content: evt.content });
                return;
              case "message_complete":
                return;
              case "interrupt":
                dispatch({ type: "INTERRUPT" });
                return;
              case "final_error":
                dispatch({ type: "ERROR", error: evt.error });
                return;
              case "done":
                return;
            }
          },
          ctrl.signal,
        );
      } catch (e) {
        if ((e as { name?: string }).name === "AbortError") return;
        const msg = e instanceof Error ? e.message : String(e);
        dispatch({ type: "ERROR", error: msg });
      } finally {
        dispatch({ type: "STREAM_END" });
      }
    },
    [],
  );

  const startFresh = useCallback(
    (userText: string, personalize: boolean, thinking: boolean) => {
      // Paint the user's bubble immediately so the chat surface has
      // conversational context as soon as it expands. The backend also
      // seeds this into checkpointer state inside _run_filter, so a
      // /results reattach sees the same first message.
      dispatch({ type: "ADD_USER", text: userText });
      return runStream({ user_text: userText, personalize, thinking });
    },
    [runStream],
  );

  const reattach = useCallback(async (threadId: string) => {
    try {
      const snap = await getChatState(threadId);
      dispatch({ type: "REPLACE_FROM_STATE", snapshot: snap });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      dispatch({ type: "ERROR", error: msg });
    }
  }, []);

  const send = useCallback(
    (resume: ResumePayload) => {
      const tid = threadIdRef.current;
      if (!tid) {
        dispatch({ type: "ERROR", error: "no active thread" });
        return Promise.resolve();
      }
      if (resume.action === "user_message") {
        dispatch({ type: "ADD_USER", text: resume.text });
      }
      return runStream({ thread_id: tid, resume });
    },
    [runStream],
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  // Cancel any in-flight stream and wipe local state. Used by the
  // home page's "refine" button: aborts the paused graph thread and
  // returns the prompt to its fresh state without a remount.
  const reset = useCallback(() => {
    abortRef.current?.abort();
    threadIdRef.current = null;
    dispatch({ type: "RESET" });
  }, []);

  return { state, startFresh, reattach, send, abort, reset };
}
