import HeroText from "@/components/ui/hero-shutter-text";
import { SidebarNav } from "@/components/sidebar-nav";
import { PromptSection } from "./_components/prompt-section";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-black text-white">
      <video
        src="/background.mp4"
        autoPlay
        muted
        loop
        playsInline
        aria-hidden="true"
        width={3840}
        height={2160}
        className="absolute inset-0 h-full w-full object-cover motion-reduce:hidden"
      />

      {/* Directional overlay — darkens the left for legibility, leaves the character clean. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-r from-black/65 via-black/20 to-transparent"
      />

      <section
        className="relative z-10 mx-auto flex min-h-screen max-w-[2160px] flex-col
          pl-[max(1.5rem,env(safe-area-inset-left))]
          pr-[max(1.5rem,env(safe-area-inset-right))]
          pt-[max(2rem,env(safe-area-inset-top))]
          pb-[max(2.5rem,env(safe-area-inset-bottom))]"
      >
        <SidebarNav />

        <div className="flex flex-1 items-center">
          <div className="max-w-[930px]">
            <h1 className="text-balance font-clash text-[66px] lowercase leading-[0.95] tracking-[-0.02em] text-white md:text-[102px] lg:text-[126px]">
              <HeroText
                text="formula"
                sliceClassNames={["text-[#442c2d]", "text-white", "text-[#442c2d]"]}
              />
            </h1>

            <p
              className="rise mt-3 max-w-[690px] font-archivo text-[22px] leading-[1.55] text-white/80 md:mt-4 md:text-[24px]"
              style={{ animationDelay: "250ms" }}
            >
              Tell us what your hair is like. We&rsquo;ll match you to brands that actually fit&nbsp;&mdash; ingredient-first, no marketing gloss.
            </p>

            <div className="mt-8 md:mt-10">
              <PromptSection />
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
