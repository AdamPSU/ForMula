"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import Loader from "@/components/ui/loader-4";
import styles from "./loading-screen.module.css";

export function LoadingScreen() {
  // Mount time of LoadingScreen == pipeline start. The screen only renders
  // once `state.phase` reaches `rerank_pending` (first step past the SQL gate),
  // so this captures elapsed pipeline time.
  const startRef = useRef<number>(Date.now());
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setElapsedMs(Date.now() - startRef.current);
    }, 100);
    return () => clearInterval(id);
  }, []);

  if (typeof document === "undefined") return null;
  return createPortal(
    <div
      className={`${styles.screen} fixed inset-0 z-50 flex flex-col items-center justify-center gap-4`}
    >
      <Loader />
      <div className="flex flex-col items-center gap-1">
        <p className="font-archivo text-[15px] font-bold text-[#442c2d]">
          don&apos;t worry, this won&apos;t take long
        </p>
        <span
          aria-live="polite"
          className="font-archivo text-[14px] tabular-nums text-[#442c2d]/70"
        >
          {(elapsedMs / 1000).toFixed(1)}s
        </span>
      </div>
    </div>,
    document.body,
  );
}
