import { type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

export async function proxy(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: [
    /*
     * Match every request path EXCEPT:
     * - _next/static, _next/image (Next.js internals)
     * - favicon.ico, image extensions, the homepage video, fonts
     */
    "/((?!_next/static|_next/image|favicon.ico|background.mp4|.*\\.(?:svg|png|jpg|jpeg|gif|webp|woff2)$).*)",
  ],
};
