"use client";

import Markdown from "react-markdown";

import { Message, MessageContent } from "@/components/ui/message";
import type { ChatMessage } from "@/lib/chat/types";

type Props = {
  message: ChatMessage;
  /** True while this message is the in-flight assistant streaming. */
  streaming?: boolean;
};

export function ChatMessageView({ message, streaming = false }: Props) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const content = message.content?.trim() ?? "";

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

  if (!content && !streaming) return null;

  return (
    <Message from="assistant">
      <MessageContent>
        {streaming && !content ? (
          <TypingDots />
        ) : (
          <AssistantMarkdown>{content}</AssistantMarkdown>
        )}
      </MessageContent>
    </Message>
  );
}

function AssistantMarkdown({ children }: { children: string }) {
  return (
    <div className="font-archivo break-words">
      <Markdown
        disallowedElements={["img", "iframe", "script", "style"]}
        unwrapDisallowed
        components={{
          p: ({ children }) => (
            <p className="mb-2 last:mb-0 leading-[1.5]">{children}</p>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="font-bold text-primary underline underline-offset-2 decoration-primary/50 hover:decoration-primary"
            >
              {children}
            </a>
          ),
          strong: ({ children }) => (
            <strong className="font-bold text-foreground">
              {children}
            </strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => (
            <ul className="mb-2 last:mb-0 list-disc pl-5 space-y-1">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-2 last:mb-0 list-decimal pl-5 space-y-1">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="leading-[1.5]">{children}</li>,
          code: ({ children }) => (
            <code className="rounded bg-foreground/10 px-1 py-0.5 text-[0.9em] font-mono">
              {children}
            </code>
          ),
        }}
      >
        {children}
      </Markdown>
    </div>
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
