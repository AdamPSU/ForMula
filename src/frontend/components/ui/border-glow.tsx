"use client";

import { useEffect, useRef, type CSSProperties, type ReactNode } from "react";
import "./border-glow.css";

interface BorderGlowProps {
  children: ReactNode;
  className?: string;
  /** RGB triplet without the `rgb()` wrapper, e.g. "255, 255, 255". */
  glowColor?: string;
  /** Radius of the radial gradient that paints the glow, in px. */
  spotlightRadius?: number;
  /** Thickness of the glowing ring, in px. */
  borderThickness?: number;
}

const BorderGlow = ({
  children,
  className = "",
  glowColor = "255, 255, 255",
  spotlightRadius = 300,
  borderThickness = 6,
}: BorderGlowProps) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Matches MagicBento's proximity ramp: full intensity within 50% of radius,
    // fades to zero at 75%.
    const proximity = spotlightRadius * 0.5;
    const fadeDistance = spotlightRadius * 0.75;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const relX = ((e.clientX - rect.left) / rect.width) * 100;
      const relY = ((e.clientY - rect.top) / rect.height) * 100;

      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const rawDistance =
        Math.hypot(e.clientX - centerX, e.clientY - centerY) -
        Math.max(rect.width, rect.height) / 2;
      const distance = Math.max(0, rawDistance);

      let intensity = 0;
      if (distance <= proximity) intensity = 1;
      else if (distance <= fadeDistance)
        intensity = (fadeDistance - distance) / (fadeDistance - proximity);

      el.style.setProperty("--glow-x", `${relX}%`);
      el.style.setProperty("--glow-y", `${relY}%`);
      el.style.setProperty("--glow-intensity", intensity.toString());
    };

    const handleMouseLeave = () => {
      el.style.setProperty("--glow-intensity", "0");
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [spotlightRadius]);

  return (
    <div
      ref={ref}
      className={`border-glow ${className}`}
      style={
        {
          "--glow-color": glowColor,
          "--glow-radius": `${spotlightRadius}px`,
          "--glow-padding": `${borderThickness}px`,
        } as CSSProperties
      }
    >
      {children}
    </div>
  );
};

export default BorderGlow;
