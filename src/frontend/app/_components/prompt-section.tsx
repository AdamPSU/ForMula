"use client";

import { PromptInputBox } from "@/components/ui/ai-prompt-box";
import BorderGlow from "@/components/ui/border-glow";

export function PromptSection() {
  return (
    <BorderGlow className="rounded-3xl">
      <PromptInputBox
        placeholder="What kind of hair are you working with?"
        onSend={(message, files) => console.log("send", { message, files })}
      />
    </BorderGlow>
  );
}
