"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

export function ToolCardQuiz() {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-[#442c2d]/15 bg-[#fbf4eb] px-3 py-2.5">
      <span
        aria-hidden="true"
        className="size-1.5 shrink-0 rounded-full bg-[#442c2d]/70"
      />
      <p className="min-w-0 flex-1 font-archivo text-[14px] text-foreground/90">
        take the hair-profile quiz — two minutes
      </p>
      <Link
        href="/quiz"
        className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-primary px-3 py-1.5 font-archivo text-[12px] text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span>start</span>
        <ArrowRight aria-hidden="true" className="size-3" />
      </Link>
    </div>
  );
}
