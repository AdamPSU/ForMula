import { getSupabaseBrowser } from "./supabase-browser";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface QuizOption {
  id: string;
  label: string;
  image?: string;
}

export interface QuizQuestion {
  id: string;
  prompt: string;
  type: "single" | "multi" | "single_image";
  maps_to: string;
  max_select?: number;
  wrap_in_list?: boolean;
  skip_value?: string;
  conditional_on?: { question_id: string; value_not_in: string[] };
  options: QuizOption[];
}

export interface Quiz {
  version: number;
  questions: QuizQuestion[];
}

export type QuizAnswers = Record<string, string | string[]>;

async function authHeaders(): Promise<HeadersInit> {
  const supabase = getSupabaseBrowser();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : {};
}

export async function authedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const auth = await authHeaders();
  return fetch(input, {
    ...init,
    headers: { ...(init.headers ?? {}), ...auth },
  });
}

export async function fetchQuiz(): Promise<Quiz> {
  const r = await fetch(`${API_URL}/quiz`);
  if (!r.ok) throw new Error(`GET /quiz: ${r.status}`);
  return r.json();
}

// Direct Supabase read under RLS. Returns null when the user has no profile.
export async function fetchProfile(): Promise<Record<string, unknown> | null> {
  const supabase = getSupabaseBrowser();
  const { data, error } = await supabase
    .from("profiles")
    .select("*")
    .maybeSingle();
  if (error) throw error;
  if (!data) return null;
  const { user_id: _user_id, updated_at: _updated_at, ...profile } =
    data as Record<string, unknown>;
  return profile;
}

export interface SessionSummary {
  id: string;
  query: string;
  status: "pending" | "complete" | "failed";
  summary: string | null;
  created_at: string;
  completed_at: string | null;
}

// Direct Supabase read under RLS.
export async function listSessions(limit = 50): Promise<SessionSummary[]> {
  const supabase = getSupabaseBrowser();
  const { data, error } = await supabase
    .from("sessions")
    .select("id, query, status, summary, created_at, completed_at")
    .order("created_at", { ascending: false })
    .limit(limit);
  if (error) throw error;
  return (data ?? []) as SessionSummary[];
}

// Direct Supabase read with joined angles, session_products, judges, and axes.
export async function fetchSession(sessionId: string) {
  const supabase = getSupabaseBrowser();
  const { data, error } = await supabase
    .from("sessions")
    .select(
      `
      id, query, status, summary, created_at, completed_at,
      session_angles ( position, angle, rationale ),
      session_products (
        id, rank, overall_score, summary, queried_at,
        products ( id, brand, name, url, category, price, ingredients, key_actives, allergens ),
        session_product_judge_panels ( judge, overall_score, summary ),
        session_product_axis_verdicts ( judge, axis, score, rationale, evidence_tokens, weaknesses, sub_criteria )
      )
      `,
    )
    .eq("id", sessionId)
    .maybeSingle();
  if (error) throw error;
  return data;
}

// Subscribe to sessions.status transitions via Realtime. Returns an unsubscribe fn.
export function subscribeSessionStatus(
  sessionId: string,
  onUpdate: (row: { status: string; summary: string | null; completed_at: string | null }) => void,
): () => void {
  const supabase = getSupabaseBrowser();
  const channel = supabase
    .channel(`session:${sessionId}`)
    .on(
      "postgres_changes",
      {
        event: "UPDATE",
        schema: "public",
        table: "sessions",
        filter: `id=eq.${sessionId}`,
      },
      (payload: { new: Record<string, unknown> }) => {
        const row = payload.new as {
          status: string;
          summary: string | null;
          completed_at: string | null;
        };
        onUpdate(row);
      },
    )
    .subscribe();
  return () => {
    void supabase.removeChannel(channel);
  };
}

export async function submitAnswers(answers: QuizAnswers): Promise<void> {
  const r = await authedFetch(`${API_URL}/profile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`POST /profile: ${r.status} ${detail}`);
  }
}

export async function clearProfile(): Promise<void> {
  await authedFetch(`${API_URL}/profile`, { method: "DELETE" });
}

export function isQuestionActive(q: QuizQuestion, answers: QuizAnswers): boolean {
  if (!q.conditional_on) return true;
  const parent = answers[q.conditional_on.question_id];
  if (parent === undefined) return false;
  const values = Array.isArray(parent) ? parent : [parent];
  const forbidden = new Set(q.conditional_on.value_not_in);
  return values.some((v) => !forbidden.has(v));
}
