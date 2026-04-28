"use client";

import { cn } from "@/lib/utils";

interface Props {
  value: string | undefined;
  onChange: (value: string) => void;
  placeholder?: string;
  maxLength?: number;
}

export function QuestionText({ value, onChange, placeholder, maxLength }: Props) {
  const current = value ?? "";
  const remaining =
    maxLength !== undefined ? maxLength - current.length : undefined;
  // Switch the counter to a warm tone in the final stretch so users can
  // see they're approaching the cap without surprise truncation.
  const nearCap = remaining !== undefined && remaining <= 80;

  return (
    <div className="flex flex-col gap-2">
      <div className="group relative">
        <textarea
          value={current}
          onChange={(e) => {
            const next = e.target.value;
            onChange(
              maxLength !== undefined && next.length > maxLength
                ? next.slice(0, maxLength)
                : next,
            );
          }}
          placeholder={placeholder}
          rows={4}
          maxLength={maxLength}
          // `field-sizing: content` (Tailwind v4) auto-grows with input
          // without JS; min-h holds an inviting starting height, max-h
          // caps before it dominates the viewport on long entries.
          className={cn(
            "field-sizing-content min-h-[140px] max-h-[280px] w-full resize-none rounded-md border bg-[#f5ebdf]/96 px-3 py-2.5 font-archivo text-sm leading-[1.5] text-[#442c2d] transition-[border-color,box-shadow] duration-150",
            "border-[#ddcbb6] placeholder:text-[#442c2d]/50",
            "hover:border-[#442c2d]/35",
            "focus:border-[#442c2d]/70 focus:outline-none focus:ring-2 focus:ring-[#e7d2b8]/70 focus:shadow-[0_18px_35px_-24px_rgba(0,0,0,0.55),inset_0_1px_0_0_rgba(255,247,237,0.7)]",
          )}
        />
      </div>
      {maxLength !== undefined && (
        <p
          aria-live="polite"
          className={cn(
            "self-end text-[11px] tabular-nums transition-colors",
            nearCap ? "text-[#f1c098]" : "text-[#f5ebdf]/64",
          )}
        >
          {current.length} / {maxLength}
        </p>
      )}
    </div>
  );
}
