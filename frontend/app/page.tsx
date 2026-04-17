"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { API_URL, authedFetch, fetchProfile } from "./lib/api";

type AppState = "idle" | "loading" | "results";

interface ProductCandidate {
  name: string;
  brand: string;
  url: string;
  ingredients: string[];
  category: string;
  price: string | null;
  key_actives: string[];
  allergens: string[];
  queried_at: string;
  overall_score: number | null;
  panel_scores: Record<string, number> | null;
  summary: string | null;
}

interface ResearchStats {
  searched: number;
  shortlisted: number;
  extracted: number;
  judged: number;
}

interface ResearchResponse {
  session_id: string;
  candidates: ProductCandidate[];
  recommendation: string | null;
  stats: ResearchStats;
}

function CloudBlob() {
  return (
    <svg
      viewBox="0 0 260 160"
      width="200"
      height="123"
      aria-hidden="true"
      className="drop-shadow-[0_10px_40px_rgba(26,14,80,0.25)]"
    >
      <defs>
        <linearGradient id="blobFill" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#9089fa" />
          <stop offset="60%" stopColor="#4f47e8" />
          <stop offset="100%" stopColor="#2f27a8" />
        </linearGradient>
      </defs>
      <path
        fill="url(#blobFill)"
        d="M63 42 C 58 22, 92 6, 112 20 C 122 6, 152 4, 164 22 C 188 12, 216 28, 210 52 C 234 60, 236 96, 210 106 C 216 130, 186 146, 166 132 C 156 150, 124 152, 114 134 C 92 146, 62 136, 62 112 C 40 108, 34 78, 54 68 C 42 58, 46 42, 63 42 Z"
      />
      <ellipse cx="108" cy="56" rx="46" ry="14" fill="rgba(255,255,255,0.18)" />
    </svg>
  );
}

export default function Home() {
  const router = useRouter();
  const [state, setState] = useState<AppState>("idle");
  const [prompt, setPrompt] = useState("");
  const [results, setResults] = useState<ProductCandidate[]>([]);
  const [recommendation, setRecommendation] = useState<string | null>(null);
  const [stats, setStats] = useState<ResearchStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gateChecked, setGateChecked] = useState(false);

  useEffect(() => {
    fetchProfile().then((p) => {
      if (p === null) {
        router.replace("/onboarding");
        return;
      }
      setGateChecked(true);
    });
  }, [router]);

  const handleSubmit = useCallback(async () => {
    if (!prompt.trim()) return;
    setState("loading");
    setError(null);
    try {
      const form = new FormData();
      form.append("prompt", prompt);
      const res = await authedFetch(`${API_URL}/research`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ResearchResponse = await res.json();
      setResults(data.candidates);
      setRecommendation(data.recommendation);
      setStats(data.stats);
      setState("results");
    } catch (err) {
      const detail = err instanceof Error ? err.message : "unknown error";
      setError(`research failed (${detail}). give it another try.`);
      setState("idle");
    }
  }, [prompt]);

  const handleReset = useCallback(() => {
    setPrompt("");
    setResults([]);
    setRecommendation(null);
    setStats(null);
    setError(null);
    setState("idle");
  }, []);

  if (!gateChecked) {
    return (
      <div className="h-[100dvh] flex items-center justify-center bg-primary text-on-primary">
        <p className="font-mono text-[0.8125rem] text-on-surface-variant">Loading…</p>
      </div>
    );
  }

  return (
    <div className="h-[100dvh] flex flex-col bg-primary text-on-primary overflow-hidden">
      <header className="shrink-0 px-8 py-2.5 flex items-center justify-between border-b border-outline-variant">
        <span className="font-title italic text-[1.2rem] tracking-tight text-secondary-container" style={{ fontWeight: 900 }}>
          formula.
        </span>
        <Link
          href="/profile"
          className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-on-surface-variant hover:text-secondary-container transition-colors"
        >
          Profile
        </Link>
      </header>

      <main className="flex-1 min-h-0 flex flex-col items-center justify-center px-6 py-6">
        {state === "idle" && (
          <div className="w-full max-w-xl fade-in flex flex-col items-center">
            <div className="mb-3">
              <CloudBlob />
            </div>
            <h1
              className="font-title italic text-secondary-container text-center leading-[0.9] tracking-[-0.02em] mb-6"
              style={{ fontSize: "clamp(3rem, 8vw, 5rem)", fontWeight: 900 }}
            >
              formula.
            </h1>

            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="what are you trying to fix, grow, or tame?"
              rows={4}
              aria-label="Describe your hair and what you're looking for"
              className="w-full resize-none bg-surface text-on-surface placeholder:text-white/50 px-5 py-4 text-[1rem] leading-relaxed rounded-[3px] border border-outline-variant focus:border-secondary-container transition-colors"
            />

            {error && (
              <p
                role="status"
                aria-live="polite"
                className="mt-3 font-mono text-[0.8125rem] text-error self-start"
              >
                {error}
              </p>
            )}

            <button
              onClick={handleSubmit}
              disabled={!prompt.trim()}
              className={`mt-6 w-full py-4 rounded-[3px] font-sans font-medium text-[0.92rem] uppercase tracking-[0.16em] transition duration-200 ${
                prompt.trim()
                  ? "bg-secondary-container text-on-secondary-container hover:brightness-[1.04] active:scale-[0.99] shadow-[0_8px_30px_rgba(242,254,139,0.28)]"
                  : "bg-surface-container-high text-white/40 cursor-not-allowed"
              }`}
            >
              find my match
            </button>
          </div>
        )}

        {state === "loading" && (
          <div className="flex flex-col items-center gap-8 fade-in text-center">
            <svg
              className="ring-spin"
              width="60"
              height="60"
              viewBox="0 0 60 60"
              fill="none"
            >
              <circle
                cx="30"
                cy="30"
                r="26"
                stroke="rgba(255,255,255,0.18)"
                strokeWidth="3"
              />
              <path
                d="M30 4 A26 26 0 0 1 56 30"
                stroke="#F4F189"
                strokeWidth="3"
                strokeLinecap="round"
              />
            </svg>
            <div>
              <p
                className="pulse-text font-serif italic font-semibold text-secondary-container mb-2"
                style={{ fontSize: "1.75rem", letterSpacing: "-0.008em" }}
              >
                reading labels…
              </p>
              <p className="font-mono text-[0.8125rem] text-on-surface-variant max-w-[320px]">
                pulling ingredient lists from the messy open web
              </p>
            </div>
          </div>
        )}

        {state === "results" && (
          <div className="w-full max-w-2xl h-full flex flex-col min-h-0">
            <div className="fade-in mb-6 shrink-0">
              <p className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-on-surface-variant mb-2">
                you asked
              </p>
              <h2 className="font-serif italic font-semibold text-secondary-container text-[1.6rem] leading-[1.2] tracking-[-0.008em] m-0 break-words text-pretty">
                {prompt}
              </h2>

              {stats && (
                <p className="mt-4 font-mono text-[0.7rem] uppercase tracking-[0.12em] text-on-surface-variant whitespace-nowrap overflow-x-auto">
                  searched{" "}
                  <span className="text-secondary-container">{stats.searched}</span>
                  {" → "}
                  shortlisted{" "}
                  <span className="text-secondary-container">{stats.shortlisted}</span>
                  {" → "}
                  judged{" "}
                  <span className="text-secondary-container">{stats.judged}</span>
                  {" → "}
                  top{" "}
                  <span className="text-secondary-container">{results.length}</span>
                </p>
              )}

              {recommendation && (
                <div className="mt-6 rounded-[3px] bg-secondary-container/15 border border-secondary-container/30 px-7 py-6">
                  <p className="font-serif italic text-secondary-container/80 text-[0.8rem] uppercase tracking-[0.08em] mb-2">
                    if you want one answer
                  </p>
                  <p className="text-[0.925rem] leading-[1.55] text-secondary-container italic">
                    {recommendation}
                  </p>
                </div>
              )}
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-5 pr-1">
              {results.length === 0 && (
                <p className="text-[0.925rem] leading-[1.55] text-on-surface">
                  nothing clean enough came back. try loosening the ask.
                </p>
              )}

              {results.map((p, i) => {
                const hostname = (() => {
                  try {
                    return new URL(p.url).hostname.replace(/^www\./, "");
                  } catch {
                    return p.url;
                  }
                })();
                return (
                  <div
                    key={i}
                    className="card-enter rounded-[3px] bg-surface-container px-6 py-5 border border-outline-variant"
                    style={{ animationDelay: `${i * 0.08}s` }}
                  >
                    <div className="flex items-start justify-between gap-4 mb-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 font-mono text-[0.7rem] uppercase tracking-[0.12em] text-on-surface-variant mb-2">
                          <span>{p.brand}</span>
                          <span>·</span>
                          <span>{p.category}</span>
                          {p.price && (
                            <>
                              <span>·</span>
                              <span>{p.price}</span>
                            </>
                          )}
                        </div>
                        <h3 className="font-serif italic font-semibold text-[1.35rem] leading-tight tracking-[-0.008em] text-secondary-container m-0 break-words text-pretty">
                          {p.name}
                        </h3>
                      </div>
                      {p.overall_score != null && (
                        <div className="shrink-0 flex flex-col items-end gap-1.5">
                          <span
                            title="Panel-averaged score (1–5)"
                            className="font-sans font-medium text-[0.78rem] px-3 py-1 rounded-[3px] bg-secondary-container text-on-secondary-container tracking-wide"
                          >
                            {p.overall_score.toFixed(2)} / 5
                          </span>
                          {p.panel_scores && (
                            <div
                              className="flex gap-1 font-mono text-[0.62rem] uppercase text-on-surface-variant"
                              style={{ letterSpacing: "0.04em" }}
                            >
                              {Object.entries(p.panel_scores).map(([judge, score]) => (
                                <span
                                  key={judge}
                                  title={`${judge} overall`}
                                  className="px-1.5 py-0.5 rounded-[3px] border border-outline-variant"
                                >
                                  {judge} {score.toFixed(1)}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="mb-4">
                      {p.summary && (
                        <p className="text-[0.925rem] leading-[1.55] text-on-surface mb-2 break-words">
                          {p.summary}
                        </p>
                      )}

                      {p.key_actives.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mb-2">
                          {p.key_actives.map((a, j) => (
                            <span
                              key={j}
                              className="text-[0.78rem] px-2.5 py-1 rounded-[3px] bg-secondary-container/25 text-secondary-container"
                            >
                              {a}
                            </span>
                          ))}
                        </div>
                      )}

                      {p.allergens.length > 0 && (
                        <p className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-on-surface-variant break-words">
                          <span className="text-secondary-container/75">watch for:</span>{" "}
                          {p.allergens.join(", ")}
                        </p>
                      )}
                    </div>

                    <div className="flex items-start justify-between gap-4">
                      <details className="min-w-0 flex-1">
                        <summary className="font-mono text-[0.72rem] uppercase tracking-[0.12em] text-on-surface-variant cursor-pointer">
                          full ingredient list ({p.ingredients.length})
                        </summary>
                        <p className="text-[0.78rem] leading-[1.55] text-on-surface mt-2 break-words">
                          {p.ingredients.join(", ")}
                        </p>
                      </details>

                      <a
                        href={p.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0 font-mono text-[0.7rem] uppercase tracking-[0.12em] text-on-surface-variant hover:text-secondary-container border-b border-outline-variant hover:border-secondary-container/60 pb-px transition-colors"
                      >
                        {hostname}
                      </a>
                    </div>
                  </div>
                );
              })}
            </div>

            <button
              onClick={handleReset}
              className="shrink-0 self-start mt-4 px-6 py-2.5 rounded-[3px] bg-transparent border border-outline text-on-surface-variant hover:border-secondary-container hover:text-secondary-container text-[0.875rem] font-sans transition-colors"
            >
              ← ask something else
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
