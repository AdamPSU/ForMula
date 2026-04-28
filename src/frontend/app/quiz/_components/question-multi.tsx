"use client";

import { cn } from "@/lib/utils";
import type { QuestionOption } from "@/lib/quiz/types";

interface Props {
  options: QuestionOption[];
  value: string[] | undefined;
  onChange: (value: string[]) => void;
  maxSelect?: number;
}

export function QuestionMulti({ options, value, onChange, maxSelect }: Props) {
  const selected = value ?? [];

  function toggle(id: string) {
    if (selected.includes(id)) {
      onChange(selected.filter((s) => s !== id));
      return;
    }
    if (maxSelect !== undefined && selected.length >= maxSelect) return;
    onChange([...selected, id]);
  }

  const twoCol = options.length >= 6;
  return (
    <div className="flex flex-col gap-2">
      {maxSelect !== undefined && (
        <p className="text-[11px] text-[#f5ebdf]/82">
          {selected.length} / {maxSelect} selected
        </p>
      )}
      <div className={cn("gap-2", twoCol ? "grid grid-cols-2" : "flex flex-col")}>
        {options.map((opt) => {
          const isSelected = selected.includes(opt.id);
          const atCap =
            !isSelected &&
            maxSelect !== undefined &&
            selected.length >= maxSelect;
          return (
            <button
              key={opt.id}
              type="button"
              onClick={() => toggle(opt.id)}
              disabled={atCap}
              className={cn(
                "rounded-md border px-4 py-2.5 text-left text-sm transition-colors",
                "border-[#ddcbb6] bg-[#f5ebdf]/96 text-[#442c2d]",
                "hover:border-[#442c2d]/35 hover:bg-[#fbf4eb]",
                isSelected &&
                  "border-[#442c2d] bg-[#e7d2b8] text-[#442c2d] shadow-[0_18px_35px_-24px_rgba(0,0,0,0.55),inset_0_1px_0_0_rgba(255,247,237,0.7)]",
                atCap &&
                  "cursor-not-allowed opacity-45 hover:border-[#ddcbb6] hover:bg-[#f5ebdf]/96",
              )}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
