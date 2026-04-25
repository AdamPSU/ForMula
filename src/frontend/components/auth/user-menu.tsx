"use client";

import { useTransition } from "react";
import { cn } from "@/lib/utils";

export function UserMenu() {
  const [pending, startTransition] = useTransition();

  function onSignOut() {
    startTransition(async () => {
      await fetch("/auth/sign-out", { method: "POST" });
      window.location.assign("/sign-in");
    });
  }

  return (
    <button
      type="button"
      onClick={onSignOut}
      disabled={pending}
      className={cn(
        // Liquid-glass recipe mirrors components/ui/ai-prompt-box.tsx: translucent
        // tint + saturated backdrop blur, hairline rim, stacked inset highlight /
        // shade + soft outer lift.
        "cursor-pointer rounded-full border border-white/20 bg-white/[0.10] px-4 py-1.5 text-sm text-white",
        "backdrop-blur-3xl backdrop-saturate-[200%] transition-colors duration-200",
        "shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35),inset_0_-1px_0_0_rgba(0,0,0,0.2),0_10px_40px_-8px_rgba(0,0,0,0.5)]",
        "hover:border-white/30 hover:bg-white/[0.14]",
        "disabled:cursor-not-allowed disabled:opacity-60",
      )}
    >
      {pending ? "…" : "sign out"}
    </button>
  );
}
