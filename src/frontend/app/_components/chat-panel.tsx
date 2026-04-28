"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ui/conversation";
import type { FilterProduct } from "@/lib/api/filter";
import type { ResumePayload } from "@/lib/chat/types";
import type { useChatSession } from "@/lib/chat/use-chat-session";

import { ChatMessageView } from "./chat-message";
import { ToolCardShortlist } from "./tool-card-shortlist";

type Session = ReturnType<typeof useChatSession>;

type Props = {
  /** The chat session hook return value, passed in by the parent. */
  session: Session;
  /** Top-N slice rendered as the inline shortlist tool card. */
  shortlist: FilterProduct[];
};

const PROMPT_SHADOW =
  "shadow-[0_8px_24px_-6px_rgba(68,44,45,0.25),inset_0_1px_0_0_rgba(255,248,239,0.75)]";

export function ChatPanel({ session, shortlist }: Props) {
  const { state, send } = session;
  const [draft, setDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const inputDisabled =
    state.isStreaming || state.isEnded || !state.threadId;

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [draft]);

  const onSubmit = () => {
    const text = draft.trim();
    if (!text || inputDisabled) return;
    setDraft("");
    const payload: ResumePayload = { action: "user_message", text };
    send(payload);
  };

  const seedMessage =
    state.messages[0]?.role === "user" ? state.messages[0] : null;

  // Index of the in-flight assistant in the *original* messages array
  // (used to drive the streaming TypingDots indicator).
  const lastIdx = state.messages.length - 1;

  return (
    <section
      aria-label="Chat"
      className={`flex h-full min-h-0 w-full flex-col overflow-hidden rounded-xl border border-[#e1cfbb] bg-[#f5ebdf] ${PROMPT_SHADOW}`}
    >
      <div
        aria-hidden
        className="h-9 bg-[#442c2d] shadow-[0_6px_12px_-2px_rgba(68,44,45,0.6)]"
      />

      <Conversation className="min-h-0 flex-1" initial={false}>
        <ConversationContent className="flex min-h-full flex-col justify-end px-4 py-4">
          {seedMessage && (
            <ChatMessageView message={seedMessage} />
          )}

          {shortlist.length > 0 && (
            <div className="max-w-[64%] py-1 sm:max-w-[52%]">
              <ToolCardShortlist top={shortlist} />
            </div>
          )}

          {state.messages.slice(1).map((m, idx) => {
            const i = idx + 1;
            return (
              <ChatMessageView
                key={i}
                message={m}
                streaming={
                  state.isStreaming && i === lastIdx && m.role === "assistant"
                }
              />
            );
          })}

          {state.error && (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2"
            >
              <p className="font-archivo text-[13px] text-destructive">
                <span className="font-medium">request failed:</span>{" "}
                {state.error}
              </p>
            </div>
          )}
        </ConversationContent>
        <ConversationScrollButton className="bottom-0 h-3.5 w-[38px] rounded-md rounded-b-none border-[#442c2d]/30 border-b-0 bg-[#442c2d] text-[#e7d2b8] shadow-[0_-2px_8px_-3px_rgba(68,44,45,0.2)] hover:bg-[#5a3a3b] [&>svg]:size-2" />
      </Conversation>

      <div className="border-t border-[#442c2d]/10 px-3 py-2">
        <div className="flex items-end gap-2 rounded-lg px-1 focus-within:ring-2 focus-within:ring-primary/70">
          <label htmlFor="chat-input" className="sr-only">
            Message
          </label>
          <textarea
            id="chat-input"
            ref={textareaRef}
            name="chat-message"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                onSubmit();
              }
            }}
            placeholder={
              state.isEnded
                ? "this chat is closed — start a new search…"
                : "ask a follow-up…"
            }
            disabled={inputDisabled}
            rows={1}
            spellCheck
            autoComplete="off"
            className="min-h-[32px] max-h-[160px] flex-1 resize-none overflow-y-auto border-none bg-transparent px-3 py-1.5 font-archivo text-[14px] text-foreground placeholder:text-foreground/55 focus:outline-none focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
          />
          <button
            type="button"
            aria-label="Send message"
            disabled={inputDisabled || draft.trim().length === 0}
            onClick={onSubmit}
            className="inline-flex size-8 shrink-0 touch-manipulation items-center justify-center rounded-full bg-primary text-primary-foreground transition-colors hover:bg-primary/85 active:bg-primary/75 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ArrowUp className="size-3.5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </section>
  );
}
