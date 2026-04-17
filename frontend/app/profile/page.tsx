"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearProfile, fetchProfile } from "../lib/api";

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProfile()
      .then((p) => {
        if (p === null) {
          router.replace("/onboarding");
          return;
        }
        setProfile(p);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [router]);

  const retake = async () => {
    const ok = window.confirm(
      "this will clear your current profile and restart the quiz. continue?",
    );
    if (!ok) return;
    await clearProfile();
    router.push("/onboarding");
  };

  if (loading || !profile) {
    return (
      <div className="h-[100dvh] flex items-center justify-center bg-primary text-on-primary">
        <p className="font-mono text-[0.8125rem] text-on-surface-variant">Loading…</p>
      </div>
    );
  }

  const entries = Object.entries(profile).filter(([k]) => k !== "free_text");

  return (
    <div className="h-[100dvh] flex flex-col bg-primary text-on-primary overflow-hidden">
      <header className="shrink-0 px-8 py-2.5 flex items-center justify-between border-b border-outline-variant">
        <Link
          href="/"
          className="font-title italic text-[1.2rem] tracking-tight text-secondary-container"
          style={{ fontWeight: 900 }}
        >
          formula.
        </Link>
        <span className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-on-surface-variant">
          your profile
        </span>
      </header>

      <main className="flex-1 min-h-0 overflow-y-auto px-6 py-10 flex justify-center">
        <div className="w-full max-w-2xl fade-in">
          <h1 className="font-serif italic font-semibold text-secondary-container text-[1.9rem] tracking-[-0.008em] leading-tight mb-8 text-pretty">
            what we know about your hair
          </h1>

          <dl className="rounded-[3px] bg-surface-container border border-outline-variant divide-y divide-outline-variant">
            {entries.map(([k, v]) => (
              <div
                key={k}
                className="grid grid-cols-[minmax(140px,180px)_1fr] gap-6 px-6 py-4"
              >
                <dt className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-on-surface-variant pt-0.5">
                  {k.replaceAll("_", " ")}
                </dt>
                <dd className="text-[0.925rem] leading-[1.55] text-on-surface break-words">
                  {Array.isArray(v) ? v.join(", ") : String(v)}
                </dd>
              </div>
            ))}
          </dl>

          <div className="mt-6 flex gap-3">
            <Link
              href="/"
              className="px-5 py-2.5 rounded-[3px] border border-outline text-on-surface-variant hover:border-secondary-container hover:text-secondary-container text-[0.875rem] transition-colors"
            >
              ← home
            </Link>
            <button
              type="button"
              onClick={retake}
              className="px-5 py-2.5 rounded-[3px] bg-secondary-container text-on-secondary-container text-[0.875rem] font-medium tracking-wide hover:brightness-[1.04]"
            >
              start over
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
