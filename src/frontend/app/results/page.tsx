"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ResultsView } from "@/app/_components/results-view";
import { RESULTS_STORAGE_KEY, type StoredResult } from "@/lib/api/filter";

function loadStored(): StoredResult | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(RESULTS_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredResult;
  } catch {
    return null;
  }
}

export default function ResultsPage() {
  const router = useRouter();
  const [data, setData] = useState<StoredResult | null>(() => loadStored());

  useEffect(() => {
    if (!data) {
      router.replace("/");
    }
  }, [data, router]);

  if (!data) return null;

  return (
    <ResultsView
      result={data.result}
      query={data.query}
      onReset={() => {
        window.sessionStorage.removeItem(RESULTS_STORAGE_KEY);
        setData(null);
        router.push("/");
      }}
    />
  );
}
