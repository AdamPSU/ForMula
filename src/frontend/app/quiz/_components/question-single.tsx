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
              "rounded-md border px-4 py-2.5 text-left text-sm transition-colors",
              "border-[#ddcbb6] bg-[#f5ebdf]/96 text-[#442c2d]",
              "hover:border-[#442c2d]/35 hover:bg-[#fbf4eb]",
              selected &&
                "border-[#442c2d] bg-[#e7d2b8] text-[#442c2d] shadow-[0_18px_35px_-24px_rgba(0,0,0,0.55),inset_0_1px_0_0_rgba(255,247,237,0.7)]",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
