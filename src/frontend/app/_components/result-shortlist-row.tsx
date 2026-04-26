import { ArrowUpRight } from "lucide-react";

import type { FilterProduct } from "@/lib/api/filter";

// Square-root transform on the raw tournament fraction.
// Raw `overall_score` is `tournament_points / (5 * R)` and structurally caps
// around 0.7–0.8 for "best in catalog" because no product wins top-2 in every
// single one of the R tournaments. The sqrt stretches the upper range so top
// contenders cluster in the 80s–90s without lying cross-query (transform is
// monotonic and deterministic).
function formatScore(p: FilterProduct): string | null {
  if (typeof p.overall_score === "number") {
    return `${Math.round(Math.sqrt(p.overall_score) * 100)}%`;
  }
  if (typeof p.relevance_score === "number") {
    return p.relevance_score.toFixed(3);
  }
  return null;
}

export function ResultShortlistRow({
  product,
  rank,
}: {
  product: FilterProduct;
  rank: number;
}) {
  const score = formatScore(product);
  const name = product.name ?? "(unnamed)";
  const subcategory = product.subcategory ?? null;

  const rowInner = (
    <>
      <span
        aria-hidden="true"
        className="font-clash text-[15px] tabular-nums text-[#442c2d]/70"
      >
        {String(rank).padStart(2, "0")}
      </span>
      <span className="min-w-0 flex-1 truncate font-archivo text-[14px] text-[#442c2d]">
        {name}
        {subcategory && (
          <span className="ml-2 text-[#442c2d]/55">· {subcategory}</span>
        )}
      </span>
      {score && (
        <span className="font-archivo text-[12px] tabular-nums text-[#442c2d]/70">
          {score}
        </span>
      )}
      {product.url && (
        <ArrowUpRight
          aria-hidden="true"
          className="size-3.5 shrink-0 text-[#442c2d]/45 transition-transform group-hover/row:-translate-y-[1px] group-hover/row:translate-x-[1px]"
        />
      )}
    </>
  );

  return (
    <li className="border-b border-[#442c2d]/10 last:border-b-0">
      {product.url ? (
        <a
          href={product.url}
          target="_blank"
          rel="noreferrer"
          className="group/row flex items-baseline gap-3 px-4 py-2.5 transition-colors duration-150 hover:bg-[#442c2d]/[0.04] focus-visible:bg-[#442c2d]/[0.06] focus-visible:outline-none"
        >
          {rowInner}
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      ) : (
        <div className="flex items-baseline gap-3 px-4 py-2.5">{rowInner}</div>
      )}
    </li>
  );
}
