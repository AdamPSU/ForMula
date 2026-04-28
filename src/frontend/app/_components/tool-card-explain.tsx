"use client";

import { ArrowUpRight } from "lucide-react";

import type { FilterProduct } from "@/lib/api/filter";

export function ToolCardExplain({
  productId,
  axesSummary,
  topSignals,
  products,
}: {
  productId: string;
  axesSummary?: string;
  topSignals?: string[];
  products: FilterProduct[];
}) {
  const product = products.find((p) => p.id === productId);
  const name = product?.name ?? "(unknown product)";
  const subcategory = product?.subcategory;
  const url = product?.url;
  const rank = product?.final_rank ?? product?.rank;

  return (
    <div className="rounded-lg border border-[#442c2d]/15 bg-[#fbf4eb] px-3 py-2.5">
      <div className="flex items-baseline gap-2">
        <p className="min-w-0 flex-1 truncate font-archivo text-[15px] font-medium text-foreground">
          {name}
          {subcategory && (
            <span className="ml-1.5 font-normal text-foreground/70">
              · {subcategory}
            </span>
          )}
        </p>
        {typeof rank === "number" && (
          <span className="shrink-0 font-archivo text-[11px] tabular-nums text-foreground/70">
            rank {rank}
          </span>
        )}
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 rounded text-foreground/70 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="View product (opens in new tab)"
          >
            <ArrowUpRight aria-hidden="true" className="size-3.5" />
          </a>
        )}
      </div>
      {(axesSummary || (topSignals && topSignals.length > 0)) && (
        <div className="mt-1.5 space-y-1.5">
          {axesSummary && (
            <p className="font-archivo text-[13px] leading-[1.5] text-foreground/85">
              {axesSummary}
            </p>
          )}
          {topSignals && topSignals.length > 0 && (
            <ul className="flex flex-wrap gap-1">
              {topSignals.map((signal) => (
                <li
                  key={signal}
                  className="rounded-md bg-secondary px-2 py-0.5 font-archivo text-[12px] text-secondary-foreground"
                >
                  {signal}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
