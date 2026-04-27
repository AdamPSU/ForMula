"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { PromptInputBox } from "@/components/ui/ai-prompt-box";
import BorderGlow from "@/components/ui/border-glow";
import {
  runFilter,
  type FilterResponse,
  RESULTS_STORAGE_KEY,
} from "@/lib/api/filter";
import { LoadingScreen } from "./loading-screen";

export function PromptSection() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [personalize, setPersonalize] = useState(true);

  if (loading) return <LoadingScreen />;

  return (
    <div className="space-y-6">
      <BorderGlow className="rounded-3xl">
        <PromptInputBox
          placeholder="What kind of hair are you working with?"
          personalize={personalize}
          onPersonalizeChange={setPersonalize}
          onSend={async (message) => {
            const text = message.trim();
            if (!text) return;
            setLoading(true);
            setError(null);
            try {
              const res: FilterResponse = await runFilter(text, { personalize });
              sessionStorage.setItem(
                RESULTS_STORAGE_KEY,
                JSON.stringify({ query: text, result: res }),
              );
              router.push("/results");
            } catch (err) {
              const msg = err instanceof Error ? err.message : String(err);
              console.error("[/recommend] error:", err);
              setError(msg);
              setLoading(false);
            }
          }}
        />
      </BorderGlow>

      {error && (
        <div className="rounded-xl bg-red-950/60 px-4 py-3 ring-1 ring-red-400/40">
          <p className="font-archivo text-sm text-red-100">
            <span className="font-medium">request failed:</span> {error}
          </p>
        </div>
      )}
    </div>
  );
}
