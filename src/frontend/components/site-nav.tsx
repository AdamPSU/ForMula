import { Fragment } from "react";
import { Home as HomeIcon } from "lucide-react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { UserMenu } from "@/components/auth/user-menu";

interface Crumb {
  label: string;
  href: string;
}

export function SiteNav({ trail }: { trail: Crumb[] }) {
  return (
    <nav
      className="absolute inset-x-0 top-0 z-20 flex items-center justify-between px-6 md:px-12 lg:px-20"
      style={{
        paddingLeft: "max(1.5rem, env(safe-area-inset-left))",
        paddingRight: "max(1.5rem, env(safe-area-inset-right))",
        paddingTop: "max(1rem, env(safe-area-inset-top))",
      }}
    >
      <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink href="/">
              <HomeIcon className="size-4" />
            </BreadcrumbLink>
          </BreadcrumbItem>
          {trail.map((c) => (
            <Fragment key={c.href}>
              <BreadcrumbSeparator>
                <div className="mx-1 size-1 rounded-full bg-white/40" />
              </BreadcrumbSeparator>
              <BreadcrumbItem>
                <BreadcrumbLink href={c.href}>{c.label}</BreadcrumbLink>
              </BreadcrumbItem>
            </Fragment>
          ))}
        </BreadcrumbList>
      </Breadcrumb>

      <UserMenu />
    </nav>
  );
}
