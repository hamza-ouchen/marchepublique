"use client";

import { PageHeader } from "@/components/PageHeader";
import { HitlBadge, LangueBadge } from "@/components/Badge";
import { getUserHistorique } from "@/lib/api";

export default function UserHistorique() {
  const userHistorique = getUserHistorique();
  return (
    <div>
      <PageHeader
        title="Historique"
        subtitle="Toutes vos conversations avec CONCIERGE sur WhatsApp."
      />

      <div className="space-y-4">
        {userHistorique.map((c) => (
          <div key={c.id} className="card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <p className="text-xs text-sand-900/40">
                {new Date(c.horodatage).toLocaleString("fr-FR")}
              </p>
              <div className="flex items-center gap-2">
                <LangueBadge langue={c.langue} />
                <HitlBadge status={c.hitlStatus} />
              </div>
            </div>
            <div className="mt-4 space-y-2 border-t border-sand-100 pt-4">
              <p className="text-sm">
                <span className="font-medium text-sand-900/50">Vous — </span>
                <span className="text-sand-900">{c.dernierMessage}</span>
              </p>
              <p className="text-sm">
                <span className="font-medium text-sand-900/50">CONCIERGE — </span>
                <span className="text-sand-900">{c.reponse}</span>
              </p>
            </div>
          </div>
        ))}
        {userHistorique.length === 0 && (
          <p className="text-sm text-sand-900/50">Aucune conversation pour l&apos;instant.</p>
        )}
      </div>
    </div>
  );
}
