"use client";

import HeroText from "@/components/ui/hero-shutter-text";
import { SiteNav } from "@/components/site-nav";
import type { FilterResponse } from "@/lib/api/filter";

import { ResultShortlistRow } from "./result-shortlist-row";

const QUERY_TRUNCATE = 60;
const TOP_N = 15;

const PROMPT_SHADOW =
  "shadow-[0_22px_50px_-22px_rgba(0,0,0,0.55),inset_0_1px_0_0_rgba(255,248,239,0.75)]";

function methodLabel(result: FilterResponse): string {
  if (result.judged) return "judged";
  if (result.reranked) return "reranked";
  return "sql order";
}

function truncateQuery(q: string): string {
  const trimmed = q.trim();
  if (trimmed.length <= QUERY_TRUNCATE) return trimmed;
  return `${trimmed.slice(0, QUERY_TRUNCATE - 1).trimEnd()}…`;
}

export function ResultsView({
  result,
  query,
  onReset,
}: {
  result: FilterResponse;
  query: string;
  onReset: () => void;
}) {
  const hasMatches = result.count > 0;
  const top = result.products.slice(0, TOP_N);
  const overflow = Math.max(0, result.count - top.length);
  const heroText = hasMatches ? String(result.count) : "nothing";
  const subtitle = hasMatches
    ? `matches · ${methodLabel(result)} · for: ${truncateQuery(query)}`
    : `matched. try a different query — for: ${truncateQuery(query)}`;

  return (
    <main className="relative min-h-screen overflow-hidden bg-black text-white">
      <video
        src="/page-two.mp4"
        autoPlay
        muted
        loop
        playsInline
        aria-hidden="true"
        width={3840}
        height={2160}
        className="absolute inset-0 h-full w-full object-cover motion-reduce:hidden"
      />

      {/* Mirrored gradient — darkens the right edge for legibility against the right-anchored column. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-l from-black/65 via-black/20 to-transparent"
      />

      <SiteNav trail={[{ label: "matches", href: "/" }]} />

      <section
        className="relative z-10 mx-auto flex min-h-screen max-w-[2160px] flex-col px-6 pb-10 md:px-12 md:pb-14 lg:px-20"
        style={{
          paddingLeft: "max(1.5rem, env(safe-area-inset-left))",
          paddingRight: "max(1.5rem, env(safe-area-inset-right))",
          paddingBottom: "max(2.5rem, env(safe-area-inset-bottom))",
        }}
      >
        <div className="flex flex-1 items-center">
          <div className="ml-auto flex max-w-[560px] flex-col items-end text-right">
            <h1 className="text-balance font-clash text-[66px] lowercase leading-[0.95] tracking-[-0.02em] text-white md:text-[102px] lg:text-[126px]">
              <HeroText
                text={heroText}
                sliceClassNames={[
                  "text-[#442c2d]",
                  "text-white",
                  "text-[#442c2d]",
                ]}
              />
            </h1>

            <p
              className="rise mt-3 max-w-[520px] font-archivo text-[18px] leading-[1.55] text-white/80 md:mt-4 md:text-[22px]"
              style={{ animationDelay: "250ms" }}
            >
              {subtitle}
            </p>

            {hasMatches && (
              <div
                className={`rise mt-8 w-full overflow-hidden rounded-3xl border border-[#e1cfbb] bg-[#f5ebdf]/97 text-left md:mt-10 ${PROMPT_SHADOW}`}
                style={{ animationDelay: "500ms" }}
              >
                <div className="flex items-baseline justify-between border-b border-[#442c2d]/10 px-4 py-2.5">
                  <span className="font-archivo text-[10px] uppercase tracking-[0.32em] text-[#442c2d]/65">
                    shortlist
                  </span>
                  {overflow > 0 && (
                    <span className="font-archivo text-[10px] uppercase tracking-[0.2em] text-[#442c2d]/55 tabular-nums">
                      top {top.length} of {result.count}
                    </span>
                  )}
                </div>
                <ol className="max-h-[42vh] overflow-y-auto">
                  {top.map((product, i) => (
                    <ResultShortlistRow
                      key={product.id}
                      product={product}
                      rank={i + 1}
                    />
                  ))}
                </ol>
              </div>
            )}

            <div
              className="rise mt-6 flex justify-end"
              style={{ animationDelay: "750ms" }}
            >
              <button
                type="button"
                onClick={onReset}
                className="group inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/5 px-5 py-3 font-archivo text-[14px] tracking-[0.04em] text-white backdrop-blur transition-colors duration-200 hover:border-white/50 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
              >
                <span
                  aria-hidden="true"
                  className="inline-block size-1.5 rounded-full bg-white/80 transition-transform duration-200 group-hover:scale-125"
                />
                new search
              </button>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
