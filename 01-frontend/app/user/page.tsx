"use client";

import { MessageCircle, Clock, Building2 } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";
import { HitlBadge } from "@/components/Badge";
import { useAuth } from "@/lib/auth-context";
import { getUserHistorique } from "@/lib/api";

export default function UserDashboard() {
  const { user } = useAuth();
  const userHistorique = getUserHistorique();
  const enAttente = userHistorique.filter((c) => c.hitlStatus === "en_attente").length;

  return (
    <div>
      <PageHeader
        title={`Bonjour, ${user?.nom?.split(" ")[0] ?? ""}`}
        subtitle={user?.entreprise ?? "Votre espace Sou9na"}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Conversations" value={userHistorique.length} icon={MessageCircle} />
        <StatCard label="En attente de confirmation" value={enAttente} icon={Clock} />
        <StatCard label="Entreprise" value={user?.entreprise ?? "—"} icon={Building2} />
      </div>

      <div className="card mt-6 p-6">
        <h2 className="text-sm font-semibold text-sand-900">Derniers echanges avec CONCIERGE</h2>
        <ul className="mt-4 divide-y divide-sand-100">
          {userHistorique.map((c) => (
            <li key={c.id} className="flex items-start justify-between gap-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm text-sand-900">{c.dernierMessage}</p>
                <p className="mt-0.5 text-xs text-sand-900/40">
                  {new Date(c.horodatage).toLocaleDateString("fr-FR")}
                </p>
              </div>
              <HitlBadge status={c.hitlStatus} />
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-6 rounded-xl border border-brand-200 bg-brand-50/60 p-5 text-sm text-brand-800">
        CONCIERGE repond sur WhatsApp. Les reponses marquees <strong>En attente</strong> sont en
        cours de verification humaine avant confirmation.
      </div>
    </div>
  );
}
