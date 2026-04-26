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
        "cursor-pointer rounded-full border border-[#e1cfbb] bg-[#f5ebdf]/97 px-4 py-1.5 text-sm text-[#442c2d]",
        "transition-colors duration-200 shadow-[0_22px_50px_-22px_rgba(0,0,0,0.55),inset_0_1px_0_0_rgba(255,248,239,0.75)]",
        "hover:border-[#442c2d]/35 hover:bg-[#fbf4eb]",
        "disabled:cursor-not-allowed disabled:opacity-60",
      )}
    >
      {pending ? "…" : "sign out"}
    </button>
  );
}
