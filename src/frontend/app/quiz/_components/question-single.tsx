"use client";

import { cn } from "@/lib/utils";
import type { QuestionOption } from "@/lib/quiz/types";

interface Props {
  options: QuestionOption[];
  value: string | undefined;
  onChange: (value: string) => void;
}

export function QuestionSingle({ options, value, onChange }: Props) {
  const twoCol = options.length >= 6;
  return (
    <div className={cn("gap-2", twoCol ? "grid grid-cols-2" : "flex flex-col")}>
      {options.map((opt) => {
        const selected = value === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            onClick={() => onChange(opt.id)}
            className={cn(
              "rounded-xl border px-4 py-2.5 text-left text-sm transition-colors",
              "border-white/15 bg-white/5 text-white/85 backdrop-blur-md",
              "hover:border-white/30 hover:bg-white/[0.09]",
              selected &&
                "border-white/70 bg-white/[0.14] text-white shadow-[inset_0_1px_0_0_rgba(255,255,255,0.25)]",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
