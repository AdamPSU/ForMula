import { Home as HomeIcon } from "lucide-react";
import Link from "next/link";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative flex min-h-[100dvh] w-full flex-col overflow-hidden bg-black text-white md:flex-row">
      <Link
        href="/"
        aria-label="home"
        className="absolute left-6 top-6 z-20 text-white/70 transition hover:text-white md:left-10 md:top-8"
        style={{
          left: "max(1.5rem, env(safe-area-inset-left))",
          top: "max(1.5rem, env(safe-area-inset-top))",
        }}
      >
        <HomeIcon className="size-6" />
      </Link>

      <section className="flex flex-1 items-center justify-center px-6 py-20 md:p-12 lg:p-16">
        {children}
      </section>

      <section className="relative hidden flex-1 p-4 md:block">
        <div className="absolute inset-4 overflow-hidden rounded-3xl">
          <video
            src="/background.mp4"
            autoPlay
            muted
            loop
            playsInline
            aria-hidden="true"
            width={3840}
            height={2160}
            className="h-full w-full object-cover motion-reduce:hidden"
          />
        </div>
      </section>
    </main>
  );
}
