"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ResultsView } from "@/app/_components/results-view";
import { CHAT_THREAD_KEY } from "@/lib/chat/types";

export default function ResultsPage() {
  const router = useRouter();
  // Start at null on both server and client so the initial markup matches.
  // The client-only effect below reads sessionStorage and either populates
  // the threadId or kicks the user back to /.
  const [threadId, setThreadId] = useState<string | null>(null);

  useEffect(() => {
    const id = window.sessionStorage.getItem(CHAT_THREAD_KEY);
    if (!id) router.replace("/");
    else setThreadId(id);
  }, [router]);

  if (!threadId) return null;

  return <ResultsView threadId={threadId} />;
}
