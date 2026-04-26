"use client";

import Image from "next/image";
import { cn } from "@/lib/utils";
import type { QuestionOption } from "@/lib/quiz/types";

interface Props {
  options: QuestionOption[];
  value: string | undefined;
  onChange: (value: string) => void;
}

export function QuestionImage({ options, value, onChange }: Props) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {options.map((opt) => {
        const selected = value === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            onClick={() => onChange(opt.id)}
            className={cn(
              "group relative flex flex-col overflow-hidden rounded-xl border bg-[#f5ebdf]/96 transition-colors",
              "border-[#ddcbb6] hover:border-[#442c2d]/35",
              selected && "border-[#442c2d] ring-2 ring-[#e7d2b8]/80",
            )}
          >
            {opt.image && (
              <div className="relative aspect-[5/4] w-full overflow-hidden">
                <Image
                  src={opt.image}
                  alt={opt.label}
                  fill
                  className="object-cover transition-transform duration-300 group-hover:scale-105"
                  sizes="(max-width: 640px) 50vw, 240px"
                />
              </div>
            )}
            <div
              className={cn(
                "flex items-center justify-center px-2 py-1.5 text-center text-xs font-medium lowercase transition-colors",
                selected
                  ? "bg-[#e7d2b8] text-[#442c2d]"
                  : "bg-[#f5ebdf] text-[#442c2d] group-hover:bg-[#fbf4eb]",
              )}
            >
              {opt.label.toLowerCase()}
            </div>
          </button>
        );
      })}
    </div>
  );
}
