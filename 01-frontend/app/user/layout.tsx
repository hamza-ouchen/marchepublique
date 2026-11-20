"use client";

import { LayoutDashboard, History, UserCircle } from "lucide-react";
import { RequireRole } from "@/components/RequireRole";
import { Sidebar, NavItem } from "@/components/Sidebar";
import { useLanguage } from "@/lib/i18n";

export default function UserLayout({ children }: { children: React.ReactNode }) {
  const { t } = useLanguage();

  const items: NavItem[] = [
    { href: "/user", label: t("nav.dashboard"), icon: LayoutDashboard },
    { href: "/user/historique", label: t("nav.history"), icon: History },
    { href: "/user/profil", label: t("nav.profile"), icon: UserCircle },
  ];

  return (
    <RequireRole role="user">
      <div className="flex min-h-screen bg-sand-50">
        <Sidebar items={items} />
        <main className="flex-1 overflow-y-auto px-8 py-8">{children}</main>
      </div>
    </RequireRole>
  );
}
