import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/** The role union mirrors the OpenAI chat schema we use throughout. */
export type MessageRole = "system" | "user" | "assistant" | "tool";

export type MessageProps = HTMLAttributes<HTMLDivElement> & {
  from: MessageRole;
};

export const Message = ({ className, from, ...props }: MessageProps) => (
  <div
    role="article"
    aria-roledescription="message"
    className={cn(
      "group flex h-fit w-full shrink-0 items-end justify-end gap-2 py-1",
      from === "user" ? "is-user" : "is-assistant flex-row-reverse justify-end",
      "[&>div]:max-w-[75%]",
      className,
    )}
    {...props}
  />
);

export type MessageContentProps = HTMLAttributes<HTMLDivElement>;

export const MessageContent = ({
  children,
  className,
  ...props
}: MessageContentProps) => (
  <div
    className={cn(
      "flex flex-col gap-2 overflow-hidden rounded-lg px-4 py-3 text-[15px] leading-[1.5] break-words shadow-[0_4px_10px_-2px_rgba(68,44,45,0.45)]",
      "group-[.is-user]:bg-primary group-[.is-user]:text-primary-foreground group-[.is-user]:rounded-br-sm",
      "group-[.is-assistant]:bg-[#fbf4eb] group-[.is-assistant]:text-foreground group-[.is-assistant]:border group-[.is-assistant]:border-[#442c2d]/15 group-[.is-assistant]:rounded-bl-sm",
      className,
    )}
    {...props}
  >
    {children}
  </div>
);
