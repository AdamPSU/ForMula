"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  fetchQuiz,
  isQuestionActive,
  submitAnswers,
  type Quiz,
  type QuizAnswers,
} from "../lib/api";

export default function OnboardingPage() {
  const router = useRouter();
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [answers, setAnswers] = useState<QuizAnswers>({});
  const [idx, setIdx] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchQuiz().then(setQuiz).catch((e) => setError(String(e)));
  }, []);

  const activeQuestions = useMemo(() => {
    if (!quiz) return [];
    return quiz.questions.filter((q) => isQuestionActive(q, answers));
  }, [quiz, answers]);

  const current = activeQuestions[idx];
  const isLast = idx === activeQuestions.length - 1;

  const selectSingle = useCallback(
    (qid: string, value: string) => {
      setAnswers((prev) => ({ ...prev, [qid]: value }));
    },
    [],
  );

  const toggleMulti = useCallback((qid: string, value: string, max?: number) => {
    setAnswers((prev) => {
      const cur = (prev[qid] as string[] | undefined) ?? [];
      const next = cur.includes(value)
        ? cur.filter((v) => v !== value)
        : max && cur.length >= max
        ? cur
        : [...cur, value];
      return { ...prev, [qid]: next };
    });
  }, []);

  const canAdvance = useMemo(() => {
    if (!current) return false;
    const a = answers[current.id];
    if (current.type === "multi") return Array.isArray(a) && a.length > 0;
    return typeof a === "string" && a.length > 0;
  }, [current, answers]);

  const advance = useCallback(async () => {
    if (!quiz || !current) return;
    if (!isLast) {
      setIdx((i) => i + 1);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await submitAnswers(answers);
      router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  }, [quiz, current, isLast, answers, router]);

  if (!quiz || !current) {
    return (
      <div className="h-[100dvh] flex items-center justify-center bg-primary text-on-primary">
        <p className="font-mono text-[0.8125rem] text-on-surface-variant">
          {error ?? "Loading…"}
        </p>
      </div>
    );
  }

  const progress = ((idx + 1) / activeQuestions.length) * 100;

  return (
    <div className="h-[100dvh] flex flex-col bg-primary text-on-primary overflow-hidden">
      <header className="shrink-0 px-8 py-2.5 flex items-center border-b border-outline-variant">
        <span className="font-title italic text-[1.2rem] tracking-tight text-secondary-container" style={{ fontWeight: 900 }}>
          formula.
        </span>
      </header>

      <div className="shrink-0 h-1 bg-surface-container">
        <div
          className="h-full bg-secondary-container transition-[width] duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>

      <main className="flex-1 min-h-0 overflow-y-auto px-6 py-6 flex justify-center">
        <div
          className={`w-full fade-in ${
            current.type === "single_image" ? "max-w-5xl" : "max-w-2xl"
          }`}
        >
          <p className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-on-surface-variant mb-3">
            step {idx + 1} of {activeQuestions.length}
          </p>

          <h1
            id="question-prompt"
            className="font-serif italic font-semibold text-secondary-container leading-tight tracking-[-0.008em] text-[1.9rem] mb-6 break-words text-pretty"
          >
            {current.prompt}
          </h1>

          {current.type === "multi" && current.max_select && (
            <p className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-on-surface-variant mb-4">
              choose up to {current.max_select}
            </p>
          )}

          <div
            role={current.type === "multi" ? "group" : "radiogroup"}
            aria-labelledby="question-prompt"
            className={
              current.type === "single_image"
                ? "grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2"
                : "flex flex-col gap-2.5"
            }
          >
            {current.options.map((opt) => {
              const a = answers[current.id];
              const selected =
                current.type === "multi"
                  ? Array.isArray(a) && a.includes(opt.id)
                  : a === opt.id;
              const isMulti = current.type === "multi";
              const onClick = () =>
                isMulti
                  ? toggleMulti(current.id, opt.id, current.max_select)
                  : selectSingle(current.id, opt.id);

              if (current.type === "single_image") {
                return (
                  <button
                    key={opt.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={onClick}
                    className={`rounded-[3px] border p-2 text-left transition ${
                      selected
                        ? "border-secondary-container bg-secondary-container/20"
                        : "border-outline-variant bg-surface hover:border-secondary-container/60"
                    }`}
                  >
                    {opt.image && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={opt.image}
                        alt={opt.label}
                        width={240}
                        height={240}
                        loading="lazy"
                        className="w-full aspect-square object-cover rounded-[2px] mb-1.5 bg-surface-container"
                      />
                    )}
                    <span className="font-sans text-[0.8rem] leading-tight block break-words">
                      {opt.label}
                    </span>
                  </button>
                );
              }

              return (
                <button
                  key={opt.id}
                  type="button"
                  role={isMulti ? "checkbox" : "radio"}
                  aria-checked={selected}
                  onClick={onClick}
                  className={`rounded-[3px] px-5 py-3.5 text-left text-[0.95rem] border transition break-words ${
                    selected
                      ? "border-secondary-container bg-secondary-container/20 text-secondary-container"
                      : "border-outline-variant bg-surface text-on-surface hover:border-secondary-container/60"
                  }`}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>

          {error && (
            <p
              role="status"
              aria-live="polite"
              className="mt-4 font-mono text-[0.8125rem] text-error"
            >
              {error}
            </p>
          )}

          <div className="mt-8 max-w-xl mx-auto flex items-center justify-between gap-4">
            <button
              onClick={() => setIdx((i) => Math.max(0, i - 1))}
              disabled={idx === 0}
              className="px-5 py-2.5 rounded-[3px] border border-outline text-on-surface-variant disabled:opacity-30 hover:border-secondary-container hover:text-secondary-container text-[0.875rem] transition-colors"
            >
              ← back
            </button>
            <button
              onClick={advance}
              disabled={!canAdvance || submitting}
              className={`px-8 py-3 rounded-[3px] font-sans font-medium text-[0.92rem] uppercase tracking-[0.16em] transition ${
                canAdvance && !submitting
                  ? "bg-secondary-container text-on-secondary-container hover:brightness-[1.04] active:scale-[0.99]"
                  : "bg-surface-container-high text-white/40 cursor-not-allowed"
              }`}
            >
              {submitting ? "saving…" : isLast ? "all done" : "next"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
