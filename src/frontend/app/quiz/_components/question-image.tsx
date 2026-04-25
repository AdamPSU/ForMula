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
              "group relative flex flex-col overflow-hidden rounded-xl border backdrop-blur-md transition-colors",
              "border-white/15 hover:border-white/30",
              selected && "border-white/80 ring-2 ring-white/40",
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
                  ? "bg-white/90 text-black"
                  : "bg-white/[0.08] text-white/85 group-hover:bg-white/[0.12]",
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
