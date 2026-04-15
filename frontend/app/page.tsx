"use client";

import { useState, useRef, useCallback, DragEvent, ChangeEvent } from "react";

type AppState = "idle" | "loading" | "results";

interface UploadedImage {
  file: File;
  preview: string;
}

interface ProductCandidate {
  name: string;
  brand: string;
  url: string;
  ingredients: string[];
  category: string;
  price: string | null;
  key_actives: string[];
  allergens: string[];
  queried_at: string;
  overall_score: number | null;
  summary: string | null;
}

interface ResearchResponse {
  candidates: ProductCandidate[];
  recommendation: string | null;
}

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [state, setState] = useState<AppState>("idle");
  const [prompt, setPrompt] = useState("");
  const [images, setImages] = useState<UploadedImage[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [results, setResults] = useState<ProductCandidate[]>([]);
  const [recommendation, setRecommendation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const addImages = useCallback((files: FileList | File[]) => {
    const arr = Array.from(files).filter((f) => f.type.startsWith("image/"));
    const newImages = arr.map((file) => ({
      file,
      preview: URL.createObjectURL(file),
    }));
    setImages((prev) => [...prev, ...newImages]);
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      if (e.dataTransfer.files.length) addImages(e.dataTransfer.files);
    },
    [addImages]
  );

  const handleFileChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      if (e.target.files?.length) addImages(e.target.files);
    },
    [addImages]
  );

  const removeImage = useCallback((index: number) => {
    setImages((prev) => {
      URL.revokeObjectURL(prev[index].preview);
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!prompt.trim()) return;
    setState("loading");
    setError(null);
    try {
      const form = new FormData();
      form.append("prompt", prompt);
      images.forEach((img) => form.append("images", img.file));
      const res = await fetch(`${API_URL}/research`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ResearchResponse = await res.json();
      setResults(data.candidates);
      setRecommendation(data.recommendation);
      setState("results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setState("idle");
    }
  }, [prompt, images]);

  const handleReset = useCallback(() => {
    images.forEach((img) => URL.revokeObjectURL(img.preview));
    setImages([]);
    setPrompt("");
    setResults([]);
    setRecommendation(null);
    setError(null);
    setState("idle");
  }, [images]);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&display=swap');

        .ring {
          animation: spin 2s linear infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        .pulse-text {
          animation: fadePulse 2s ease-in-out infinite;
        }
        @keyframes fadePulse {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 1; }
        }
        .fade-in {
          animation: fadeIn 0.4s ease forwards;
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .card-enter {
          opacity: 0;
          animation: cardIn 0.4s ease forwards;
        }
        @keyframes cardIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div
        className="min-h-screen flex flex-col"
        style={{
          background: "#F6F3EE",
          color: "#1A1A18",
          fontFamily: "var(--font-geist-sans), sans-serif",
        }}
      >
        {/* Header */}
        <header
          className="px-8 py-5 flex items-center justify-between"
          style={{ borderBottom: "1px solid rgba(26,26,24,0.08)" }}
        >
          <span
            style={{
              fontFamily: "'Instrument Serif', Georgia, serif",
              fontSize: "1.25rem",
              letterSpacing: "-0.01em",
            }}
          >
            ForMula
          </span>
          <span
            style={{
              fontSize: "0.75rem",
              color: "rgba(26,26,24,0.4)",
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              fontFamily: "var(--font-geist-mono), monospace",
            }}
          >
            Research
          </span>
        </header>

        {/* Main */}
        <main className="flex-1 flex flex-col items-center justify-center px-6 py-16">
          {/* ── IDLE ── */}
          {state === "idle" && (
            <div className="w-full max-w-2xl fade-in">
              <h1
                style={{
                  fontFamily: "'Instrument Serif', Georgia, serif",
                  fontSize: "clamp(2rem, 5vw, 3rem)",
                  lineHeight: 1.15,
                  letterSpacing: "-0.02em",
                  marginBottom: "2.5rem",
                  color: "#1A1A18",
                }}
              >
                What would you like
                <br />
                <em>to research?</em>
              </h1>

              {/* Textarea */}
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Describe your hair and what you're looking for…"
                rows={4}
                style={{
                  width: "100%",
                  background: "#FDFAF6",
                  border: "1.5px solid rgba(26,26,24,0.12)",
                  borderRadius: "10px",
                  padding: "1rem 1.125rem",
                  fontSize: "1rem",
                  lineHeight: "1.6",
                  color: "#1A1A18",
                  resize: "none",
                  outline: "none",
                  fontFamily: "var(--font-geist-sans), sans-serif",
                  boxSizing: "border-box",
                  transition: "border-color 0.2s",
                }}
                onFocus={(e) =>
                  (e.target.style.borderColor = "rgba(26,26,24,0.4)")
                }
                onBlur={(e) =>
                  (e.target.style.borderColor = "rgba(26,26,24,0.12)")
                }
              />

              {/* Image drop zone */}
              <div className="mt-4">
                <div
                  onDrop={handleDrop}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    border: `1.5px dashed ${
                      isDragging
                        ? "rgba(26,26,24,0.5)"
                        : "rgba(26,26,24,0.18)"
                    }`,
                    borderRadius: "10px",
                    padding: "1.125rem",
                    cursor: "pointer",
                    transition: "all 0.2s",
                    background: isDragging
                      ? "rgba(26,26,24,0.03)"
                      : "transparent",
                    textAlign: "center",
                  }}
                >
                  <p
                    style={{
                      fontSize: "0.8125rem",
                      color: "rgba(26,26,24,0.4)",
                      margin: 0,
                      fontFamily: "var(--font-geist-mono), monospace",
                    }}
                  >
                    {isDragging
                      ? "Drop images here"
                      : "Attach images (optional) — drag & drop or click"}
                  </p>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleFileChange}
                  style={{ display: "none" }}
                />

                {images.length > 0 && (
                  <div className="flex flex-wrap gap-3 mt-3">
                    {images.map((img, i) => (
                      <div
                        key={i}
                        style={{
                          position: "relative",
                          display: "inline-block",
                        }}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={img.preview}
                          alt={img.file.name}
                          style={{
                            width: "72px",
                            height: "72px",
                            objectFit: "cover",
                            borderRadius: "8px",
                            border: "1.5px solid rgba(26,26,24,0.1)",
                            display: "block",
                          }}
                        />
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            removeImage(i);
                          }}
                          style={{
                            position: "absolute",
                            top: "-6px",
                            right: "-6px",
                            width: "18px",
                            height: "18px",
                            borderRadius: "50%",
                            background: "#1A1A18",
                            color: "#F6F3EE",
                            border: "none",
                            cursor: "pointer",
                            fontSize: "11px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            lineHeight: 1,
                          }}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {error && (
                <p
                  style={{
                    marginTop: "1rem",
                    fontSize: "0.8125rem",
                    color: "#b54040",
                    fontFamily: "var(--font-geist-mono), monospace",
                  }}
                >
                  {error}
                </p>
              )}

              {/* Submit */}
              <button
                onClick={handleSubmit}
                disabled={!prompt.trim()}
                style={{
                  marginTop: "1.5rem",
                  width: "100%",
                  padding: "0.875rem",
                  background: prompt.trim()
                    ? "#1A1A18"
                    : "rgba(26,26,24,0.1)",
                  color: prompt.trim()
                    ? "#F6F3EE"
                    : "rgba(26,26,24,0.3)",
                  border: "none",
                  borderRadius: "10px",
                  fontSize: "0.9375rem",
                  fontWeight: 500,
                  cursor: prompt.trim() ? "pointer" : "not-allowed",
                  transition: "all 0.2s",
                  fontFamily: "var(--font-geist-sans), sans-serif",
                  letterSpacing: "0.01em",
                }}
              >
                Research →
              </button>
            </div>
          )}

          {/* ── LOADING ── */}
          {state === "loading" && (
            <div
              className="flex flex-col items-center gap-8 fade-in"
              style={{ textAlign: "center" }}
            >
              <div
                style={{ position: "relative", width: "56px", height: "56px" }}
              >
                <svg
                  className="ring"
                  width="56"
                  height="56"
                  viewBox="0 0 56 56"
                  fill="none"
                >
                  <circle
                    cx="28"
                    cy="28"
                    r="24"
                    stroke="rgba(26,26,24,0.08)"
                    strokeWidth="2"
                  />
                  <path
                    d="M28 4 A24 24 0 0 1 52 28"
                    stroke="#1A1A18"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              </div>

              <div>
                <p
                  className="pulse-text"
                  style={{
                    fontFamily: "'Instrument Serif', Georgia, serif",
                    fontSize: "1.5rem",
                    letterSpacing: "-0.01em",
                    margin: "0 0 0.5rem",
                  }}
                >
                  Researching…
                </p>
                <p
                  style={{
                    fontSize: "0.8125rem",
                    color: "rgba(26,26,24,0.4)",
                    fontFamily: "var(--font-geist-mono), monospace",
                    margin: 0,
                    maxWidth: "320px",
                  }}
                >
                  Sourcing products with verified ingredient lists
                </p>
              </div>
            </div>
          )}

          {/* ── RESULTS ── */}
          {state === "results" && (
            <div className="w-full max-w-2xl">
              {/* Query recap */}
              <div className="fade-in" style={{ marginBottom: "2rem" }}>
                <p
                  style={{
                    fontSize: "0.75rem",
                    color: "rgba(26,26,24,0.4)",
                    fontFamily: "var(--font-geist-mono), monospace",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    marginBottom: "0.375rem",
                    margin: "0 0 0.375rem",
                  }}
                >
                  Query
                </p>
                <h2
                  style={{
                    fontFamily: "'Instrument Serif', Georgia, serif",
                    fontSize: "1.625rem",
                    lineHeight: 1.3,
                    letterSpacing: "-0.01em",
                    margin: 0,
                  }}
                >
                  {prompt}
                </h2>
                {images.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {images.map((img, i) => (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        key={i}
                        src={img.preview}
                        alt=""
                        style={{
                          width: "40px",
                          height: "40px",
                          objectFit: "cover",
                          borderRadius: "6px",
                          border: "1px solid rgba(26,26,24,0.1)",
                        }}
                      />
                    ))}
                  </div>
                )}
                {recommendation && (
                  <p
                    style={{
                      marginTop: "1rem",
                      fontSize: "0.875rem",
                      color: "rgba(26,26,24,0.6)",
                      fontStyle: "italic",
                    }}
                  >
                    {recommendation}
                  </p>
                )}
              </div>

              <div
                style={{
                  height: "1px",
                  background: "rgba(26,26,24,0.1)",
                  marginBottom: "2rem",
                }}
              />

              {/* Result cards */}
              <div className="flex flex-col gap-6">
                {results.length === 0 && (
                  <p
                    style={{
                      fontSize: "0.875rem",
                      color: "rgba(26,26,24,0.5)",
                      fontFamily: "var(--font-geist-mono), monospace",
                    }}
                  >
                    No products matched your criteria.
                  </p>
                )}
                {results.map((p, i) => {
                  const hostname = (() => {
                    try {
                      return new URL(p.url).hostname.replace(/^www\./, "");
                    } catch {
                      return p.url;
                    }
                  })();
                  return (
                    <div
                      key={i}
                      className="card-enter"
                      style={{
                        animationDelay: `${i * 0.1}s`,
                        paddingBottom: "1.5rem",
                        borderBottom:
                          i < results.length - 1
                            ? "1px solid rgba(26,26,24,0.07)"
                            : "none",
                      }}
                    >
                      {/* brand + category + price row */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "0.5rem",
                          fontSize: "0.7rem",
                          fontFamily: "var(--font-geist-mono), monospace",
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          color: "rgba(26,26,24,0.5)",
                          marginBottom: "0.375rem",
                        }}
                      >
                        <span>{p.brand}</span>
                        <span>·</span>
                        <span>{p.category}</span>
                        {p.price && (
                          <>
                            <span>·</span>
                            <span>{p.price}</span>
                          </>
                        )}
                      </div>

                      <div
                        style={{
                          display: "flex",
                          alignItems: "baseline",
                          justifyContent: "space-between",
                          gap: "0.75rem",
                          margin: "0 0 0.625rem",
                        }}
                      >
                        <h3
                          style={{
                            fontFamily: "'Instrument Serif', Georgia, serif",
                            fontSize: "1.25rem",
                            lineHeight: 1.3,
                            letterSpacing: "-0.01em",
                            margin: 0,
                            color: "#1A1A18",
                          }}
                        >
                          {p.name}
                        </h3>
                        {p.overall_score != null && (
                          <span
                            title="Judge score (1–5)"
                            style={{
                              flexShrink: 0,
                              fontFamily: "var(--font-geist-mono), monospace",
                              fontSize: "0.75rem",
                              padding: "0.2rem 0.5rem",
                              borderRadius: "999px",
                              background: "#1A1A18",
                              color: "#F6F3EE",
                              letterSpacing: "0.02em",
                            }}
                          >
                            {p.overall_score.toFixed(2)} / 5
                          </span>
                        )}
                      </div>

                      {p.summary && (
                        <p
                          style={{
                            fontSize: "0.875rem",
                            lineHeight: 1.55,
                            color: "rgba(26,26,24,0.75)",
                            margin: "0 0 0.75rem",
                          }}
                        >
                          {p.summary}
                        </p>
                      )}

                      {p.key_actives.length > 0 && (
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "0.375rem",
                            marginBottom: "0.75rem",
                          }}
                        >
                          {p.key_actives.map((a, j) => (
                            <span
                              key={j}
                              style={{
                                fontSize: "0.75rem",
                                padding: "0.2rem 0.5rem",
                                borderRadius: "999px",
                                background: "rgba(26,26,24,0.06)",
                                color: "rgba(26,26,24,0.75)",
                              }}
                            >
                              {a}
                            </span>
                          ))}
                        </div>
                      )}

                      <details style={{ marginBottom: "0.625rem" }}>
                        <summary
                          style={{
                            fontSize: "0.75rem",
                            fontFamily: "var(--font-geist-mono), monospace",
                            color: "rgba(26,26,24,0.5)",
                            cursor: "pointer",
                            letterSpacing: "0.04em",
                          }}
                        >
                          Ingredients ({p.ingredients.length})
                        </summary>
                        <p
                          style={{
                            fontSize: "0.8125rem",
                            lineHeight: 1.6,
                            color: "rgba(26,26,24,0.65)",
                            margin: "0.5rem 0 0",
                          }}
                        >
                          {p.ingredients.join(", ")}
                        </p>
                      </details>

                      {p.allergens.length > 0 && (
                        <p
                          style={{
                            fontSize: "0.75rem",
                            color: "rgba(26,26,24,0.5)",
                            fontFamily: "var(--font-geist-mono), monospace",
                            margin: "0 0 0.625rem",
                          }}
                        >
                          Allergens: {p.allergens.join(", ")}
                        </p>
                      )}

                      <a
                        href={p.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          fontSize: "0.75rem",
                          fontFamily: "var(--font-geist-mono), monospace",
                          color: "rgba(26,26,24,0.4)",
                          textDecoration: "none",
                          borderBottom: "1px solid rgba(26,26,24,0.15)",
                          paddingBottom: "1px",
                          transition: "color 0.15s",
                        }}
                        onMouseOver={(e) =>
                          ((e.currentTarget as HTMLAnchorElement).style.color =
                            "#1A1A18")
                        }
                        onMouseOut={(e) =>
                          ((e.currentTarget as HTMLAnchorElement).style.color =
                            "rgba(26,26,24,0.4)")
                        }
                      >
                        {hostname}
                      </a>
                    </div>
                  );
                })}
              </div>

              {/* Start over */}
              <button
                onClick={handleReset}
                style={{
                  marginTop: "2.5rem",
                  padding: "0.625rem 1.25rem",
                  background: "transparent",
                  border: "1.5px solid rgba(26,26,24,0.2)",
                  borderRadius: "8px",
                  fontSize: "0.875rem",
                  color: "rgba(26,26,24,0.55)",
                  cursor: "pointer",
                  fontFamily: "var(--font-geist-sans), sans-serif",
                  transition: "all 0.2s",
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.borderColor = "rgba(26,26,24,0.5)";
                  e.currentTarget.style.color = "#1A1A18";
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.borderColor = "rgba(26,26,24,0.2)";
                  e.currentTarget.style.color = "rgba(26,26,24,0.55)";
                }}
              >
                ← Start over
              </button>
            </div>
          )}
        </main>
      </div>
    </>
  );
}
