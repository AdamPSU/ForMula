"use client";

import { Message, MessageContent } from "@/components/ui/message";
import type { FilterProduct } from "@/lib/api/filter";
import type { ChatMessage } from "@/lib/chat/types";

import { ToolCardExplain } from "./tool-card-explain";
import { ToolCardQuiz } from "./tool-card-quiz";

type Props = {
  message: ChatMessage;
  products: FilterProduct[];
  /** True while this message is the in-flight assistant streaming. */
  streaming?: boolean;
};

export function ChatMessageView({
  message,
  products,
  streaming = false,
}: Props) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const content = message.content?.trim() ?? "";
  const hasToolCalls = !!message.tool_calls?.length;

  if (!isUser && !isAssistant) return null;

  if (isUser) {
    return (
      <Message from="user">
        <MessageContent>
          <p className="font-archivo whitespace-pre-wrap break-words">
            {content}
          </p>
        </MessageContent>
      </Message>
    );
  }

  // Assistant: bubble + optional full-width tool cards. The bubble is
  // omitted when the LLM emits ONLY a tool_call (no prose) so we don't
  // render an empty cream rectangle.
  return (
    <>
      <Message from="assistant">
        {(content || streaming) && (
          <MessageContent>
            {streaming && !content ? (
              <TypingDots />
            ) : (
              <p className="font-archivo whitespace-pre-wrap break-words">
                {content}
              </p>
            )}
          </MessageContent>
        )}
      </Message>
      {hasToolCalls && (
        <div className="mt-2 mb-3 max-w-[80%] space-y-2 sm:max-w-[65%]">
          {message.tool_calls!.map((tc) => {
            if (tc.name === "explain_product") {
              return (
                <ToolCardExplain
                  key={tc.id}
                  productId={String(tc.arguments.product_id ?? "")}
                  axesSummary={
                    typeof tc.arguments.axes_summary === "string"
                      ? (tc.arguments.axes_summary as string)
                      : undefined
                  }
                  topSignals={
                    Array.isArray(tc.arguments.top_signals)
                      ? (tc.arguments.top_signals as string[])
                      : undefined
                  }
                  products={products}
                />
              );
            }
            if (tc.name === "start_quiz") {
              return <ToolCardQuiz key={tc.id} />;
            }
            return null;
          })}
        </div>
      )}
    </>
  );
}

function TypingDots() {
  return (
    <span
      aria-label="assistant is typing"
      role="status"
      className="inline-flex items-center gap-1 py-1"
    >
      <span
        className="size-1.5 animate-bounce rounded-full bg-foreground/70 motion-reduce:animate-none"
        style={{ animationDelay: "0ms" }}
      />
      <span
        className="size-1.5 animate-bounce rounded-full bg-foreground/70 motion-reduce:animate-none"
        style={{ animationDelay: "150ms" }}
      />
      <span
        className="size-1.5 animate-bounce rounded-full bg-foreground/70 motion-reduce:animate-none"
        style={{ animationDelay: "300ms" }}
      />
    </span>
  );
}
