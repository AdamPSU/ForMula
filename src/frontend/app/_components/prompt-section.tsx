"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { PromptInputBox } from "@/components/ui/ai-prompt-box";
import BorderGlow from "@/components/ui/border-glow";
import { CHAT_THREAD_KEY } from "@/lib/chat/types";
import { useChatSession } from "@/lib/chat/use-chat-session";

export function PromptSection() {
  const router = useRouter();
  const { state, startFresh, send, reset } = useChatSession();

  const [personalize, setPersonalize] = useState(true);
  const [input, setInput] = useState("");
  const [hasSubmitted, setHasSubmitted] = useState(false);
  // Tracks the exact text last submitted, so editing the prompt
  // implicitly cancels the warning gate (re-submit = fresh query)
  // while leaving it untouched lets the submit button confirm. Held
  // in state — read during render to compute `inputUnchanged`.
  const [submittedText, setSubmittedText] = useState("");
  const pushedRef = useRef(false);

  const shouldNavigate =
    !!state.threadId && state.isWaiting && state.phase === "relay";

  useEffect(() => {
    if (!shouldNavigate || !state.threadId || pushedRef.current) return;
    pushedRef.current = true;
    sessionStorage.setItem(CHAT_THREAD_KEY, state.threadId);
    router.push("/results");
  }, [shouldNavigate, state.threadId, router]);

  const isWorking =
    hasSubmitted &&
    !state.error &&
    state.phase !== "relay" &&
    state.phase !== "awaiting_confirm";

  const isWarning = state.phase === "awaiting_confirm" && state.isWaiting;
  const inputUnchanged = input.trim() === submittedText;
  // Below 2 matches there's nothing meaningful to rank — force a refine.
  const surfaced = state.surfacedCount ?? 0;
  const rankable = surfaced >= 2;
  const confirmable = isWarning && rankable && inputUnchanged;

  const handleSend = (message: string) => {
    const text = message.trim();
    if (!text) return;
    if (confirmable) {
      send({ action: "confirm" });
      return;
    }
    setSubmittedText(text);
    setHasSubmitted(true);
    pushedRef.current = false;
    reset();
    startFresh(text, personalize);
  };

  return (
    <>
      <div className="rise" style={{ animationDelay: "500ms" }}>
        <BorderGlow className="rounded-xl">
          <PromptInputBox
            placeholder="What kind of hair are you working with?"
            personalize={personalize}
            onPersonalizeChange={setPersonalize}
            isLoading={isWorking}
            value={input}
            onValueChange={setInput}
            onSend={handleSend}
            notice={
              isWarning ? (
                <>
                  {surfaced === 0 ? (
                    <span className="text-[#442c2d] font-medium">
                      no matches
                    </span>
                  ) : (
                    <>
                      <span className="text-[#442c2d] font-medium">
                        {surfaced}
                      </span>{" "}
                      matched
                    </>
                  )}
                  {" · "}
                  {confirmable ? (
                    <span className="text-[#442c2d]">rank anyway →</span>
                  ) : (
                    <span className="text-[#442c2d]/60">edit to refine</span>
                  )}
                </>
              ) : null
            }
          />
        </BorderGlow>
      </div>

      {state.error && (
        <div className="mt-4 rounded-md bg-red-950/60 px-4 py-3 ring-1 ring-red-400/40">
          <p className="font-archivo text-sm text-red-100">
            <span className="font-medium">request failed:</span> {state.error}
          </p>
        </div>
      )}
    </>
  );
}
