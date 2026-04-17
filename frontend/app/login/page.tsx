"use client";

import { useState } from "react";
import { getSupabaseBrowser } from "../lib/supabase-browser";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setState("sending");
    setError(null);
    const supabase = getSupabaseBrowser();
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    if (error) {
      setState("error");
      setError(error.message);
      return;
    }
    setState("sent");
  };

  return (
    <div className="h-[100dvh] flex items-center justify-center bg-primary text-on-primary px-6">
      <div className="w-full max-w-md fade-in">
        <h1
          className="font-title italic text-secondary-container text-center leading-[0.9] tracking-[-0.02em] mb-8"
          style={{ fontSize: "clamp(3rem, 8vw, 5rem)", fontWeight: 900 }}
        >
          formula.
        </h1>

        {state === "sent" ? (
          <div className="text-center fade-in">
            <p className="font-serif italic text-secondary-container text-[1.4rem] leading-tight mb-3">
              check your inbox
            </p>
            <p className="font-mono text-[0.8125rem] text-on-surface-variant">
              we sent a magic link to {email}
            </p>
          </div>
        ) : (
          <form onSubmit={submit} className="flex flex-col gap-4">
            <label
              htmlFor="email"
              className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-on-surface-variant"
            >
              sign in with email
            </label>
            <input
              id="email"
              type="email"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-surface text-on-surface placeholder:text-white/40 px-5 py-4 text-[1rem] leading-relaxed rounded-[3px] border border-outline-variant focus:border-secondary-container transition-colors"
            />
            {error && (
              <p className="font-mono text-[0.8125rem] text-error">{error}</p>
            )}
            <button
              type="submit"
              disabled={!email.trim() || state === "sending"}
              className={`mt-2 w-full py-4 rounded-[3px] font-sans font-medium text-[0.92rem] uppercase tracking-[0.16em] transition ${
                email.trim() && state !== "sending"
                  ? "bg-secondary-container text-on-secondary-container hover:brightness-[1.04] active:scale-[0.99]"
                  : "bg-surface-container-high text-white/40 cursor-not-allowed"
              }`}
            >
              {state === "sending" ? "sending…" : "send magic link"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
