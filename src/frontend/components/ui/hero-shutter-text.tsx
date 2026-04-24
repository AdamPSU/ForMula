"use client";

import React from "react";
import { motion } from "framer-motion";

interface HeroTextProps {
  text?: string;
  className?: string;
  /** Color classes for the three sliding slice layers, in top/middle/bottom order. */
  sliceClassNames?: [string, string, string];
}

export default function HeroText({
  text = "IMMERSE",
  className = "",
  sliceClassNames = ["text-white/70", "text-white/40", "text-white/70"],
}: HeroTextProps) {
  const characters = text.split("");
  const [topSlice, middleSlice, bottomSlice] = sliceClassNames;

  return (
    <span
      className={`relative inline-flex flex-wrap items-baseline ${className}`}
      aria-label={text}
    >
      {characters.map((char, i) => (
        <span
          key={i}
          aria-hidden
          className="relative inline-block overflow-hidden leading-none"
        >
          <motion.span
            initial={{ opacity: 0, filter: "blur(10px)" }}
            animate={{ opacity: 1, filter: "blur(0px)" }}
            transition={{ delay: i * 0.04 + 0.3, duration: 0.8 }}
            className="inline-block leading-none"
          >
            {char === " " ? " " : char}
          </motion.span>

          <motion.span
            initial={{ x: "-100%", opacity: 0 }}
            animate={{ x: "100%", opacity: [0, 1, 0] }}
            transition={{ duration: 0.7, delay: i * 0.04, ease: "easeInOut" }}
            className={`pointer-events-none absolute inset-0 leading-none ${topSlice}`}
            style={{ clipPath: "polygon(0 0, 100% 0, 100% 35%, 0 35%)" }}
          >
            {char === " " ? " " : char}
          </motion.span>

          <motion.span
            initial={{ x: "100%", opacity: 0 }}
            animate={{ x: "-100%", opacity: [0, 1, 0] }}
            transition={{ duration: 0.7, delay: i * 0.04 + 0.1, ease: "easeInOut" }}
            className={`pointer-events-none absolute inset-0 leading-none ${middleSlice}`}
            style={{ clipPath: "polygon(0 35%, 100% 35%, 100% 65%, 0 65%)" }}
          >
            {char === " " ? " " : char}
          </motion.span>

          <motion.span
            initial={{ x: "-100%", opacity: 0 }}
            animate={{ x: "100%", opacity: [0, 1, 0] }}
            transition={{ duration: 0.7, delay: i * 0.04 + 0.2, ease: "easeInOut" }}
            className={`pointer-events-none absolute inset-0 leading-none ${bottomSlice}`}
            style={{ clipPath: "polygon(0 65%, 100% 65%, 100% 100%, 0 100%)" }}
          >
            {char === " " ? " " : char}
          </motion.span>
        </span>
      ))}
    </span>
  );
}
