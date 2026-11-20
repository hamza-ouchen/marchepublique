"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LucideIcon, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";
import clsx from "clsx";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export function Sidebar({ items }: { items: NavItem[] }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const isAdmin = user?.role === "admin";

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-sand-200 bg-surface">
      <div className="flex items-center justify-between px-5 py-5">
        <Logo />
        <ThemeToggle />
      </div>

      <div className="px-5 pb-4">
        <span
          className={clsx(
            "badge badge-dot w-fit",
            isAdmin
              ? "border border-violet-200 bg-violet-50 text-violet-700"
              : "border border-brand-100 bg-brand-50 text-brand-700"
          )}
        >
          {isAdmin ? "Espace Admin" : "Espace TPME"}
        </span>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {items.map((item) => {
          const active =
            pathname === item.href ||
            (item.href !== "/admin" && item.href !== "/user" && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? isAdmin
                    ? "bg-violet-50 text-violet-700"
                    : "bg-brand-50 text-brand-700"
                  : "text-sand-900/70 hover:bg-sand-100 hover:text-sand-900"
              )}
            >
              <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-sand-200 px-3 py-4">
        <div className="mb-2 flex items-center gap-3 rounded-lg px-3 py-2">
          <div
            className={clsx(
              "flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold",
              isAdmin ? "bg-violet-100 text-violet-700" : "bg-brand-100 text-brand-700"
            )}
          >
            {user?.nom?.[0]?.toUpperCase() ?? "?"}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-sand-900">{user?.nom}</p>
            <p className="truncate text-xs text-sand-900/50">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-sand-900/70 transition-colors hover:bg-red-50 hover:text-red-700"
        >
          <LogOut className="h-[18px] w-[18px]" />
          Deconnexion
        </button>
      </div>
    </aside>
  );
}
