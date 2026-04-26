"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

type Mode = "sign-in" | "sign-up";

interface AuthFormProps {
  mode: Mode;
}

const SIGN_IN = {
  title: "welcome back",
  description: "the formula that fits your hair.",
  cta: "sign in",
  switchHref: "/sign-up",
  switchPrompt: "new here?",
  switchLink: "create an account",
  passwordAutoComplete: "current-password",
} as const;

const SIGN_UP = {
  title: "create an account",
  description: "match your hair to formulas, ingredient-first.",
  cta: "create account",
  switchHref: "/sign-in",
  switchPrompt: "already have an account?",
  switchLink: "sign in",
  passwordAutoComplete: "new-password",
} as const;

const inputWrapper =
  "rounded-2xl border border-[#dfccb7] bg-[#f5ebdf]/96 shadow-[0_18px_40px_-22px_rgba(0,0,0,0.45),inset_0_1px_0_0_rgba(255,248,239,0.7)] transition-colors focus-within:border-[#442c2d]/35 focus-within:bg-[#fbf4eb]";

const inputBase =
  "w-full bg-transparent p-4 text-base text-[#442c2d] placeholder:text-[#442c2d]/55 focus:outline-none";

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const isSignUp = mode === "sign-up";
  const copy = isSignUp ? SIGN_UP : SIGN_IN;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setPending(true);

    const supabase = createClient();
    const { error: authError } = isSignUp
      ? await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
        })
      : await supabase.auth.signInWithPassword({ email, password });

    setPending(false);

    if (authError) {
      setError(authError.message);
      return;
    }

    if (isSignUp) {
      setInfo("check your inbox to confirm your email.");
      return;
    }

    router.replace("/");
    router.refresh();
  }

  return (
    <div className="flex w-full max-w-md flex-col gap-6">
      <div className="flex flex-col gap-3">
        <h1 className="rise font-clash text-[44px] lowercase leading-[0.95] tracking-[-0.02em] text-white">
          {copy.title}
        </h1>
        <p
          className="rise text-base text-white/70"
          style={{ animationDelay: "100ms" }}
        >
          {copy.description}
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-5">
        <label
          className="rise flex flex-col gap-2"
          style={{ animationDelay: "200ms" }}
        >
          <span className="text-sm text-white/60">email</span>
          <div className={inputWrapper}>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className={inputBase}
            />
          </div>
        </label>

        <label
          className="rise flex flex-col gap-2"
          style={{ animationDelay: "300ms" }}
        >
          <span className="text-sm text-white/60">password</span>
          <div className={inputWrapper}>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                required
                minLength={8}
                autoComplete={copy.passwordAutoComplete}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="at least 8 characters"
                className={cn(inputBase, "pr-12")}
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? "hide password" : "show password"}
                className="absolute inset-y-0 right-3 flex items-center text-[#442c2d]/60 transition-colors hover:text-[#442c2d]"
              >
                {showPassword ? (
                  <EyeOff className="size-5" />
                ) : (
                  <Eye className="size-5" />
                )}
              </button>
            </div>
          </div>
        </label>

        {error && (
          <p role="alert" className="text-sm text-red-300">
            {error}
          </p>
        )}
        {info && (
          <p role="status" className="text-sm text-[#f5ebdf]">
            {info}
          </p>
        )}

        <button
          type="submit"
          disabled={pending}
          className="rise mt-1 w-full rounded-full bg-[#f5ebdf] py-4 text-base font-medium text-[#442c2d] transition hover:bg-[#fff6ed] disabled:cursor-not-allowed disabled:opacity-60"
          style={{ animationDelay: "400ms" }}
        >
          {pending ? "…" : copy.cta}
        </button>
      </form>

      <p
        className="rise text-sm text-white/60"
        style={{ animationDelay: "500ms" }}
      >
        {copy.switchPrompt}{" "}
        <Link
          href={copy.switchHref}
          className="text-white underline-offset-4 hover:underline"
        >
          {copy.switchLink}
        </Link>
      </p>
    </div>
  );
}
