"use client";

import { useEffect, useMemo, useState } from "react";

import HeroText from "@/components/ui/hero-shutter-text";
import { SidebarNav } from "@/components/sidebar-nav";
import { getChatState } from "@/lib/api/chat";
import type { FilterProduct } from "@/lib/api/filter";
import { useChatSession } from "@/lib/chat/use-chat-session";

import { ChatPanel } from "./chat-panel";

const TOP_N = 15;

function buildSubtitle({
  surfacedCount,
  filteredCount,
  reranked,
  shownCount,
}: {
  surfacedCount: number;
  filteredCount: number;
  reranked: boolean;
  shownCount: number;
}): string {
  if (surfacedCount === 0) return "no matches. try a different query";
  const surfaced = surfacedCount.toLocaleString();
  if (filteredCount !== surfacedCount && reranked) {
    const filtered = filteredCount.toLocaleString();
    return `pulled ${surfaced} candidates, narrowed down to ${filtered} high-quality matches. here are the top ${shownCount}.`;
  }
  return `pulled ${surfaced} candidates. here are the top ${shownCount}.`;
}

export function ResultsView({ threadId }: { threadId: string }) {
  const session = useChatSession();
  const { reattach } = session;
  const [products, setProducts] = useState<FilterProduct[]>([]);
  const [surfacedCount, setSurfacedCount] = useState(0);
  const [reranked, setReranked] = useState(false);

  // One-shot reattach on mount: pulls messages, products, and pipeline flags.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const snap = await getChatState(threadId);
        if (cancelled) return;
        setProducts(snap.products);
        setSurfacedCount(snap.surfaced_count);
        setReranked(snap.reranked);
      } catch {
        // Errors surface through the chat session reattach below.
      }
    })();
    reattach(threadId);
    return () => {
      cancelled = true;
    };
  }, [threadId, reattach]);

  const top = products.slice(0, TOP_N);
  const heroText = products.length > 0 ? "results" : "nothing";
  const subtitle = useMemo(
    () =>
      buildSubtitle({
        surfacedCount,
        filteredCount: products.length,
        reranked,
        shownCount: top.length,
      }),
    [surfacedCount, products.length, reranked, top.length],
  );

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

      {/* Directional overlay — darkens the left for legibility, leaves the character clean. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-r from-black/65 via-black/20 to-transparent"
      />

      <section
        className="relative z-10 mx-auto flex h-full max-w-[2160px] flex-col
          pl-[max(1.5rem,env(safe-area-inset-left))]
          pr-[max(1.5rem,env(safe-area-inset-right))]
          pt-[max(2rem,env(safe-area-inset-top))]
          pb-[max(0.5rem,env(safe-area-inset-bottom))]"
      >
        <SidebarNav />

        {/* Page surface — hero and subtitle live above and outside
            the chat, anchored to the right column but text-aligned
            to its left edge. The negative top margin shrinks the
            hero's flex-line footprint by 10vh, which the flex-1 chat
            below absorbs as extra height (chat stays anchored to the
            section bottom). */}
        <div
          className="-mt-[10vh] w-full max-w-[700px] self-end text-left"
          style={{ transform: "translateY(-20%)" }}
        >
          <h1 className="text-balance font-clash text-[56px] lowercase leading-[0.95] tracking-[-0.02em] text-white md:text-[88px] lg:text-[104px]">
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
            className="rise mt-1 font-archivo text-[15px] leading-[1.55] text-white/75 tabular-nums md:mt-2 md:text-[17px]"
            style={{ animationDelay: "250ms" }}
          >
            {subtitle}
          </p>
        </div>

        {/* Chat dock — pulled up with a negative top margin so it
            consumes the visual gap left by the hero's translateY. */}
        <div
          className="rise -mt-[2vh] flex min-h-0 w-full max-w-[700px] flex-1 self-end"
          style={{ animationDelay: "750ms" }}
        >
          <ChatPanel
            session={session}
            products={products}
            shortlist={top}
          />
        </div>
      </section>
    </main>
  );
}
