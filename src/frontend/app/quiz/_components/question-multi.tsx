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
        <p className="text-[11px] text-white/50">
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
                "rounded-xl border px-4 py-2.5 text-left text-sm transition-colors",
                "border-white/15 bg-white/5 text-white/85 backdrop-blur-md",
                "hover:border-white/30 hover:bg-white/[0.09]",
                isSelected &&
                  "border-white/70 bg-white/[0.14] text-white shadow-[inset_0_1px_0_0_rgba(255,255,255,0.25)]",
                atCap && "cursor-not-allowed opacity-40 hover:border-white/15 hover:bg-white/5",
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
