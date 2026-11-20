"use client";

import { LayoutDashboard, MessageSquare, Users2 } from "lucide-react";
import { RequireRole } from "@/components/RequireRole";
import { Sidebar, NavItem } from "@/components/Sidebar";
import { useLanguage } from "@/lib/i18n";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { t } = useLanguage();

  const items: NavItem[] = [
    { href: "/admin", label: t("nav.dashboard"), icon: LayoutDashboard },
    { href: "/admin/conversations", label: t("nav.conversations"), icon: MessageSquare },
    { href: "/admin/clients", label: t("nav.clients"), icon: Users2 },
  ];

  return (
    <RequireRole role="admin">
      <div className="flex min-h-screen bg-sand-50">
        <Sidebar items={items} />
        <main className="flex-1 overflow-y-auto px-8 py-8">{children}</main>
      </div>
    </RequireRole>
  );
}
