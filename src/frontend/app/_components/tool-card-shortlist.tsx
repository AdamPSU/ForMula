"use client";

import { ShineBorder } from "@/components/ui/shine-border";
import type { FilterProduct } from "@/lib/api/filter";

import { ResultShortlistRow } from "./result-shortlist-row";

export function ToolCardShortlist({ top }: { top: FilterProduct[] }) {
  if (top.length === 0) return null;

  return (
    <ShineBorder
      borderRadius={8}
      borderWidth={2}
      duration={12}
      color={["#2a2954", "#a89ec5", "#2a2954"]}
      className="border border-[#442c2d]/15 bg-[#fbf4eb] p-3 shadow-[0_2px_8px_-3px_rgba(68,44,45,0.2)]"
    >
      <div className="mb-2 text-center">
        <h3 className="font-clash text-[16px] font-bold tracking-tight text-[#442c2d]">
          shortlist
        </h3>
        {top.length > 6 && (
          <p className="font-archivo text-[10px] italic text-[#442c2d]/55">
            scroll for more
          </p>
        )}
      </div>
      <div className="scrollbar-cream max-h-[10rem] space-y-1.5 overflow-y-auto pr-1 [overscroll-behavior:contain]">
        {top.map((product, i) => (
          <ResultShortlistRow
            key={product.id}
            product={product}
            rank={i + 1}
            index={i}
          />
        ))}
      </div>
    </ShineBorder>
  );
}
