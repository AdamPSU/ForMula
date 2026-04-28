"use client";

import { useEffect, useState } from "react";
import {
  motion,
  useSpring,
  useTransform,
  type MotionValue,
} from "framer-motion";

import type { FilterProduct } from "@/lib/api/filter";

// Square-root transform on the raw tournament fraction.
// Raw `overall_score` is `tournament_points / (5 * R)` and structurally caps
// around 0.7–0.8 for "best in catalog" because no product wins top-2 in every
// single one of the R tournaments. The sqrt stretches the upper range so top
// contenders cluster in the 80s–90s without lying cross-query (transform is
// monotonic and deterministic).
function scoreNumber(p: FilterProduct): number | null {
  if (typeof p.overall_score === "number") {
    return Math.round(Math.sqrt(p.overall_score) * 100);
  }
  if (typeof p.relevance_score === "number") {
    return Math.round(p.relevance_score * 100);
  }
  return null;
}

const DIGIT_FONT_SIZE = 13;
const DIGIT_PADDING = 4;
const DIGIT_HEIGHT = DIGIT_FONT_SIZE + DIGIT_PADDING;

function AnimatedScore({ end, duration = 1.2 }: { end: number; duration?: number }) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (end <= 0) return;
    const stepMs = Math.max(8, (duration / end) * 1000);
    const id = setInterval(() => {
      setValue((prev) => {
        if (prev >= end) {
          clearInterval(id);
          return prev;
        }
        return prev + 1;
      });
    }, stepMs);
    return () => clearInterval(id);
  }, [end, duration]);

  return (
    <div
      style={{ fontSize: DIGIT_FONT_SIZE }}
      className="flex overflow-hidden rounded font-archivo font-bold leading-none tabular-nums text-[#442c2d] [-webkit-text-stroke:0.75px_currentColor]"
    >
      {value >= 100 && <Digit place={100} value={value} />}
      {value >= 10 && <Digit place={10} value={value} />}
      <Digit place={1} value={value} />
      <span className="ml-0.5">%</span>
    </div>
  );
}

function Digit({ place, value }: { place: number; value: number }) {
  const valueRoundedToPlace = Math.floor(value / place);
  const animatedValue = useSpring(valueRoundedToPlace, {
    stiffness: 100,
    damping: 20,
  });

  useEffect(() => {
    animatedValue.set(valueRoundedToPlace);
  }, [animatedValue, valueRoundedToPlace]);

  return (
    <div style={{ height: DIGIT_HEIGHT }} className="relative w-[1ch] tabular-nums">
      {Array.from({ length: 10 }).map((_, i) => (
        <NumberCell key={i} mv={animatedValue} number={i} />
      ))}
    </div>
  );
}

function NumberCell({
  mv,
  number,
}: {
  mv: MotionValue<number>;
  number: number;
}) {
  const y = useTransform(mv, (latest) => {
    const placeValue = latest % 10;
    const offset = (10 + number - placeValue) % 10;
    let memo = offset * DIGIT_HEIGHT;
    if (offset > 5) memo -= 10 * DIGIT_HEIGHT;
    return memo;
  });

  return (
    <motion.span
      style={{ y }}
      className="absolute inset-0 flex items-center justify-center"
    >
      {number}
    </motion.span>
  );
}

const RANK_BADGE: Record<number, string> = {
  1: "bg-[#b87c95] text-[#fff8ef]",
  2: "bg-[#a89ec5] text-[#fff8ef]",
  3: "bg-[#2a2954] text-[#fff8ef]",
};

const RANK_BAR: Record<number, string> = {
  1: "bg-[#7d4a5d]",
  2: "bg-[#5e5483]",
  3: "bg-[#14133a]",
};

export function ResultShortlistRow({
  product,
  rank,
  index,
}: {
  product: FilterProduct;
  rank: number;
  index: number;
}) {
  const score = scoreNumber(product);
  const name = product.name ?? "(unnamed)";
  const brand = product.brand_name ?? null;
  const badge = RANK_BADGE[rank] ?? "bg-[#442c2d] text-[#fff8ef]";
  const barColor = RANK_BAR[rank] ?? "bg-[#442c2d]";

  const inner = (
    <>
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <div
          className={`flex size-7 shrink-0 items-center justify-center rounded-full font-sans text-[12px] font-black tabular-nums leading-none ${badge}`}
        >
          {rank}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <p className="truncate font-archivo text-[12px] font-semibold leading-tight tracking-tight text-[#442c2d]">
            {name}
          </p>
          {brand && (
            <p className="truncate font-archivo text-[10px] leading-tight text-[#442c2d]/55">
              {brand}
            </p>
          )}
        </div>
      </div>
      {score !== null && <AnimatedScore end={score} />}
    </>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08, ease: "easeOut" }}
    >
      <div className="rounded-md border border-[#442c2d]/15 bg-[#fbf4eb] transition-colors duration-200 hover:bg-[#442c2d]/[0.04]">
        {product.url ? (
          <a
            href={product.url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-between gap-2 px-2.5 py-1.5 focus-visible:outline-none"
          >
            {inner}
            <span className="sr-only">(opens in a new tab)</span>
          </a>
        ) : (
          <div className="flex items-center justify-between gap-2 px-2.5 py-1.5">
            {inner}
          </div>
        )}
      </div>

      {score !== null && (
        <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-[#442c2d]/10">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${score}%` }}
            transition={{
              duration: 0.8,
              delay: index * 0.08 + 0.2,
              ease: [0.25, 0.1, 0.25, 1],
            }}
            className={`h-full rounded-full ${barColor}`}
          />
        </div>
      )}
    </motion.div>
  );
}
