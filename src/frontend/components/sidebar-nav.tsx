"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Droplets, Home, Info, Settings } from "lucide-react";

import { Tabs, TabsList, TabsTab } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { value: "/", label: "home", icon: Home },
  { value: "/quiz", label: "hair quiz", icon: Droplets },
  { value: "/info", label: "info", icon: Info },
  { value: "/settings", label: "settings", icon: Settings },
] as const;

function activeValue(pathname: string): string {
  if (pathname.startsWith("/quiz")) return "/quiz";
  if (pathname.startsWith("/info")) return "/info";
  if (pathname.startsWith("/settings")) return "/settings";
  return "/";
}

const ROW_CLASS = "h-[34px] gap-[8px] px-[12px] text-[14px] lowercase sm:h-[34px] sm:text-[14px]";

export function SidebarNav() {
  const pathname = usePathname();
  const value = activeValue(pathname);

  return (
    <nav aria-label="Primary" className="w-fit">
      <div className="w-fit border-s border-white/20">
        <Tabs orientation="vertical" value={value}>
          <TabsList
            variant="underline"
            className={cn(
              "text-white/55",
              "[&_[data-slot=tab-indicator]]:bg-white",
            )}
          >
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <TabsTab
                  key={item.value}
                  value={item.value}
                  nativeButton={false}
                  render={<Link href={item.value} />}
                  className={cn(
                    ROW_CLASS,
                    "hover:bg-transparent hover:text-white/85",
                    "data-active:text-white",
                  )}
                >
                  <Icon className="size-[16px]" aria-hidden />
                  {item.label}
                </TabsTab>
              );
            })}
          </TabsList>
        </Tabs>
      </div>
    </nav>
  );
}
