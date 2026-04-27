"use client";

import HeroText from "@/components/ui/hero-shutter-text";
import { SidebarNav } from "@/components/sidebar-nav";
import type { FilterResponse } from "@/lib/api/filter";

import { ResultShortlistRow } from "./result-shortlist-row";

const TOP_N = 15;

const PROMPT_SHADOW =
  "shadow-[0_22px_50px_-22px_rgba(0,0,0,0.55),inset_0_1px_0_0_rgba(255,248,239,0.75)]";

function buildSubtitle(result: FilterResponse, shownCount: number): string {
  if (result.surfaced_count === 0) return "no matches. try a different query";
  const surfaced = result.surfaced_count.toLocaleString();
  if (result.surfaced_count !== result.count) {
    const filtered = result.count.toLocaleString();
    const stageLabel = result.judged ? "judged" : "ranked";
    return `${surfaced} products surfaced, narrowed to ${filtered} ${stageLabel}. showing top ${shownCount}`;
  }
  return `${surfaced} products surfaced. showing top ${shownCount}`;
}

export function ResultsView({
  result,
  onReset,
}: {
  result: FilterResponse;
  query: string;
  onReset: () => void;
}) {
  const hasMatches = result.count > 0;
  const top = result.products.slice(0, TOP_N);
  const overflow = Math.max(0, result.count - top.length);
  const heroText = hasMatches ? "results" : "nothing";
  const subtitle = buildSubtitle(result, top.length);

  return (
    <main className="relative h-screen overflow-hidden bg-black text-white">
      <video
        src="/page-two.mp4"
        autoPlay
        muted
        loop
        playsInline
        aria-hidden="true"
        width={3840}
        height={2160}
        className="fixed inset-x-0 top-0 h-screen w-full object-cover object-top motion-reduce:hidden"
      />

      {/* Mirrored gradient — darkens the right edge for legibility against the right-anchored column. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-l from-black/65 via-black/20 to-transparent"
      />

      <section
        className="relative z-10 mx-auto flex h-full max-w-[2160px] flex-col px-6 pt-8 pb-10 md:px-12 md:pt-10 md:pb-14 lg:px-20"
        style={{
          paddingLeft: "max(1.5rem, env(safe-area-inset-left))",
          paddingRight: "max(1.5rem, env(safe-area-inset-right))",
          paddingTop: "max(2rem, env(safe-area-inset-top))",
          paddingBottom: "max(2.5rem, env(safe-area-inset-bottom))",
        }}
      >
        <SidebarNav />

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
              className="rise mt-3 max-w-[520px] font-archivo text-[16px] leading-[1.55] text-white/75 tabular-nums md:mt-4 md:text-[18px]"
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
