"use client";

import { LayoutDashboard, History, UserCircle } from "lucide-react";
import { RequireRole } from "@/components/RequireRole";
import { Sidebar, NavItem } from "@/components/Sidebar";

const items: NavItem[] = [
  { href: "/user", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/user/historique", label: "Historique", icon: History },
  { href: "/user/profil", label: "Mon profil", icon: UserCircle },
];

export default function UserLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireRole role="user">
      <div className="flex min-h-screen bg-sand-50">
        <Sidebar items={items} />
        <main className="flex-1 overflow-y-auto px-8 py-8">{children}</main>
      </div>
    </RequireRole>
  );
}
