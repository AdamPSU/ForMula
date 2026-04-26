"use client";

import { createPortal } from "react-dom";

import Loader from "@/components/ui/loader-4";
import styles from "./loading-screen.module.css";

export function LoadingScreen() {
  if (typeof document === "undefined") return null;
  return createPortal(
    <div
      className={`${styles.screen} fixed inset-0 z-50 flex items-center justify-center`}
    >
      <Loader />
    </div>,
    document.body,
  );
}
