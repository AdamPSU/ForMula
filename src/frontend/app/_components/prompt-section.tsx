"use client";

import { useState } from "react";

import { PromptInputBox } from "@/components/ui/ai-prompt-box";
import BorderGlow from "@/components/ui/border-glow";
import { runFilter, type FilterResponse } from "@/lib/api/filter";

export function PromptSection() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FilterResponse | null>(null);

  return (
    <div className="space-y-6">
      <BorderGlow className="rounded-3xl">
        <PromptInputBox
          placeholder="What kind of hair are you working with?"
          onSend={async (message) => {
            const text = message.trim();
            if (!text) return;
            setLoading(true);
            setError(null);
            try {
              const res = await runFilter(text);
              setResult(res);
            } catch (err) {
              setError(err instanceof Error ? err.message : String(err));
              setResult(null);
            } finally {
              setLoading(false);
            }
          }}
        />
      </BorderGlow>

      {loading && (
        <p className="text-sm text-white/70 font-archivo">Searching…</p>
      )}
      {error && (
        <p className="text-sm text-red-300 font-archivo">{error}</p>
      )}
      {result && !loading && <ResultsList result={result} />}
    </div>
  );
}

function ResultsList({ result }: { result: FilterResponse }) {
  if (result.count === 0) {
    return (
      <p className="text-sm text-white/70 font-archivo">
        No products matched. Try rephrasing.
      </p>
    );
  }

  const visible = result.products.slice(0, 25);

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between text-xs text-white/60 font-archivo">
        <span>
          {result.count} {result.count === 1 ? "match" : "matches"}
          {result.reranked ? " · ranked by ingredient fit" : " · unranked (no hair profile)"}
        </span>
        {visible.length < result.count && (
          <span>showing top {visible.length}</span>
        )}
      </div>
      <ul className="space-y-2">
        {visible.map((p) => (
          <li
            key={p.id}
            className="rounded-2xl bg-white/5 backdrop-blur p-4 ring-1 ring-white/10"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="font-archivo text-[15px] text-white truncate">
                  {p.name ?? "(unnamed)"}
                </div>
                <div className="mt-0.5 text-xs text-white/60 font-archivo">
                  {[p.subcategory, p.category].filter(Boolean).join(" · ") || "—"}
                </div>
                {p.description && (
                  <p className="mt-2 text-xs text-white/70 font-archivo line-clamp-2">
                    {p.description}
                  </p>
                )}
              </div>
              <div className="flex flex-col items-end gap-1 shrink-0">
                {typeof p.relevance_score === "number" && (
                  <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] tabular-nums text-white/80 font-archivo">
                    {p.relevance_score.toFixed(3)}
                  </span>
                )}
                {p.url && (
                  <a
                    href={p.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] underline text-white/70 hover:text-white font-archivo"
                  >
                    view
                  </a>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
