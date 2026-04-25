import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { SiteNav } from "@/components/site-nav";
import type { Quiz } from "@/lib/quiz/types";
import { QuizFlow } from "./_components/quiz-flow";

// Read quiz.json server-side per-request. The file is a symlink into the
// backend (single source of truth); reading via fs follows the symlink at
// runtime and avoids Turbopack's refusal to bundle paths outside the
// project root.
function loadQuiz(): Quiz {
  return JSON.parse(
    readFileSync(resolve(process.cwd(), "lib/quiz/quiz.json"), "utf8"),
  ) as Quiz;
}

export default function QuizPage() {
  const quiz = loadQuiz();
  return (
    <main className="relative min-h-screen overflow-hidden bg-black text-white">
      <video
        src="/quiz.mp4"
        autoPlay
        muted
        loop
        playsInline
        aria-hidden="true"
        className="absolute inset-0 h-full w-full object-cover motion-reduce:hidden"
      />

      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-black/55"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,rgba(0,0,0,0.45)_70%,rgba(0,0,0,0.7)_100%)]"
      />

      <SiteNav trail={[{ label: "quiz", href: "/quiz" }]} />

      <section
        className="relative z-10 mx-auto flex min-h-screen max-w-[1400px] flex-col px-6 pb-4 md:px-12 md:pb-6 lg:px-20"
        style={{
          paddingLeft: "max(1.5rem, env(safe-area-inset-left))",
          paddingRight: "max(1.5rem, env(safe-area-inset-right))",
          paddingBottom: "max(1rem, env(safe-area-inset-bottom))",
        }}
      >
        <div className="flex flex-1 items-center justify-center py-2">
          <QuizFlow quiz={quiz} />
        </div>
      </section>
    </main>
  );
}
