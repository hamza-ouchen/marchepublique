"use client";

import { LayoutDashboard, MessageSquare, Users2 } from "lucide-react";
import { RequireRole } from "@/components/RequireRole";
import { Sidebar, NavItem } from "@/components/Sidebar";

const items: NavItem[] = [
  { href: "/admin", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/admin/conversations", label: "Conversations", icon: MessageSquare },
  { href: "/admin/clients", label: "Clients (TPME)", icon: Users2 },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireRole role="admin">
      <div className="flex min-h-screen bg-sand-50">
        <Sidebar items={items} />
        <main className="flex-1 overflow-y-auto px-8 py-8">{children}</main>
      </div>
    </RequireRole>
  );
}
