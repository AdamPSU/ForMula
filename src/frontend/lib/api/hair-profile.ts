import { createClient } from "@/lib/supabase/client";
import type { HairProfile } from "@/lib/quiz/types";

export async function submitHairProfile(
  profile: HairProfile,
  quizVersion: number,
): Promise<{ id: string }> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("not signed in");

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) throw new Error("NEXT_PUBLIC_API_URL is not set");

  const res = await fetch(`${apiUrl}/me/hair-profile`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({ quiz_version: quizVersion, profile }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`submit failed (${res.status}): ${text}`);
  }
  return res.json() as Promise<{ id: string }>;
}
