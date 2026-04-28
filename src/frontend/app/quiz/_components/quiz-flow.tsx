"use client";

import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight } from "lucide-react";

import { cn } from "@/lib/utils";
import type {
  AnswerValue,
  Answers,
  HairProfile,
  Question,
  Quiz,
} from "@/lib/quiz/types";
import { submitHairProfile } from "@/lib/api/hair-profile";
import { QuestionSingle } from "./question-single";
import { QuestionMulti } from "./question-multi";
import { QuestionImage } from "./question-image";
import { QuestionText } from "./question-text";

function isVisible(q: Question, answers: Answers): boolean {
  if (!q.conditional_on) return true;
  const dep = answers[q.conditional_on.question_id];
  if (dep === undefined) return false;
  const depArr = Array.isArray(dep) ? dep : [dep];
  // Visible when at least one selected value is OUTSIDE the skip set.
  return depArr.some((v) => !q.conditional_on!.value_not_in.includes(v));
}

function canAdvance(q: Question, value: AnswerValue | undefined): boolean {
  if (q.type === "text") {
    // Optional text → always advanceable (skip allowed). Required text →
    // need a non-empty trimmed value.
    if (q.optional) return true;
    return typeof value === "string" && value.trim().length > 0;
  }
  if (value === undefined) return false;
  if (q.type === "multi") {
    const arr = value as string[];
    // "concerns" is the only multi where 0 selections is acceptable —
    // a user with no top hair concerns can move past it.
    if (q.id === "concerns") return true;
    return arr.length >= 1;
  }
  return typeof value === "string" && value.length > 0;
}

function buildProfile(quiz: Quiz, answers: Answers): HairProfile {
  const profile: Record<string, AnswerValue> = {};
  for (const q of quiz.questions) {
    let val: AnswerValue | undefined;
    if (!isVisible(q, answers)) {
      if (q.skip_value === undefined) {
        throw new Error(`question ${q.id} is hidden but has no skip_value`);
      }
      val = q.skip_value;
    } else {
      val = answers[q.id];
      // Optional text questions: trim, and omit the key entirely when
      // blank so the POST body has no story field. Pydantic's
      // `story: str | None = None` accepts the absence cleanly.
      if (q.type === "text") {
        const s = typeof val === "string" ? val.trim() : "";
        if (s.length === 0) {
          if (q.optional) continue;
          throw new Error(`missing answer for ${q.id}`);
        }
        profile[q.maps_to] = s;
        continue;
      }
      if (val === undefined) {
        throw new Error(`missing answer for ${q.id}`);
      }
    }
    if (q.wrap_in_list && typeof val === "string") val = [val];
    profile[q.maps_to] = val;
  }
  return profile as unknown as HairProfile;
}

export function QuizFlow({ quiz }: { quiz: Quiz }) {
  const router = useRouter();
  const [answers, setAnswers] = useState<Answers>({});
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const visible = useMemo(
    () => quiz.questions.filter((q) => isVisible(q, answers)),
    [quiz, answers],
  );
  const total = visible.length;
  const clampedStep = Math.min(step, total - 1);
  const current = visible[clampedStep];
  const isLast = clampedStep === total - 1;
  const value = answers[current.id];
  const advanceOk = canAdvance(current, value);

  function setAnswer(v: AnswerValue) {
    setAnswers((a) => ({ ...a, [current.id]: v }));
  }

  function back() {
    setStep((s) => Math.max(0, s - 1));
  }

  function submit(finalAnswers: Answers) {
    setError(null);
    startTransition(async () => {
      try {
        const profile = buildProfile(quiz, finalAnswers);
        await submitHairProfile(profile, quiz.version);
        router.push("/");
        router.refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "submit failed");
      }
    });
  }

  // Single-select questions advance on click; the multi question still uses Next.
  function selectAndAdvance(v: AnswerValue) {
    const nextAnswers = { ...answers, [current.id]: v };
    setAnswers(nextAnswers);
    if (isLast) {
      submit(nextAnswers);
      return;
    }
    setStep((s) => s + 1);
  }

  function next() {
    if (!advanceOk) return;
    if (isLast) {
      submit(answers);
      return;
    }
    setStep((s) => s + 1);
  }

  return (
    <div className="flex w-full max-w-[480px] flex-col gap-4">
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between text-[11px] text-[#f5ebdf]/78">
          <span>
            {clampedStep + 1} / {total}
          </span>
          <span className="font-clash lowercase">hair intake</span>
        </div>
        <div className="h-px w-full bg-[#f5ebdf]/24">
          <div
            className="h-px bg-[#f5ebdf] transition-[width] duration-300"
            style={{ width: `${((clampedStep + 1) / total) * 100}%` }}
          />
        </div>
      </div>

      <div key={current.id} className="rise flex flex-col gap-3">
        <h1 className="font-clash text-xl lowercase leading-[1.05] tracking-[-0.02em] text-white md:text-[22px]">
          {current.prompt}
        </h1>

        {current.type === "single" && (
          <QuestionSingle
            options={current.options}
            value={value as string | undefined}
            onChange={selectAndAdvance}
          />
        )}
        {current.type === "multi" && (
          <QuestionMulti
            options={current.options}
            value={value as string[] | undefined}
            onChange={setAnswer}
            maxSelect={current.max_select}
          />
        )}
        {current.type === "single_image" && (
          <QuestionImage
            options={current.options}
            value={value as string | undefined}
            onChange={selectAndAdvance}
          />
        )}
        {current.type === "text" && (
          <QuestionText
            value={value as string | undefined}
            onChange={setAnswer}
            placeholder={current.placeholder}
            maxLength={current.max_length}
          />
        )}
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-300">
          {error}
        </p>
      )}

      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={back}
          disabled={clampedStep === 0 || pending}
          className={cn(
            "flex items-center gap-1.5 rounded-xl border border-[#ddcbb6] bg-[#f5ebdf]/96 px-4 py-2 text-xs text-[#442c2d] transition-colors",
            "hover:border-[#442c2d]/35 hover:bg-[#fbf4eb]",
            "disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-[#ddcbb6] disabled:hover:bg-[#f5ebdf]/96",
          )}
        >
          <ArrowLeft className="size-3.5" />
          back
        </button>

        {(current.type === "multi" || current.type === "text") && (
          <button
            type="button"
            onClick={next}
            disabled={!advanceOk || pending}
            className={cn(
              "flex items-center gap-1.5 rounded-xl bg-[#f5ebdf] px-5 py-2 text-xs font-medium text-[#442c2d] transition-colors",
              "hover:bg-[#fff6ed]",
              "disabled:cursor-not-allowed disabled:opacity-40",
            )}
          >
            {pending ? "…" : isLast ? "submit" : "next"}
            {!pending && !isLast && <ArrowRight className="size-3.5" />}
          </button>
        )}
      </div>
    </div>
  );
}
