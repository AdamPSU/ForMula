import { createClient } from "@/lib/supabase/client";

export type FilterProduct = {
  id: string;
  name?: string | null;
  subcategory?: string | null;
  category?: string | null;
  description?: string | null;
  price?: number | null;
  currency?: string | null;
  url?: string | null;
  brand_id?: string | null;
  relevance_score?: number;
  rank?: number;
  [key: string]: unknown;
};

export type FilterResponse = {
  products: FilterProduct[];
  count: number;
  sql: string;
  params: unknown[];
  reranked: boolean;
};

export async function runFilter(text: string): Promise<FilterResponse> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("not signed in");

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) throw new Error("NEXT_PUBLIC_API_URL is not set");

  const res = await fetch(`${apiUrl}/filter`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`/filter ${res.status}: ${body}`);
  }
  return res.json() as Promise<FilterResponse>;
}
