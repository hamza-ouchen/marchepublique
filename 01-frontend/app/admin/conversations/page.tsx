"use client";

import { useState } from "react";
import { Check, X } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { HitlBadge, LangueBadge } from "@/components/Badge";
import { getConversations } from "@/lib/api";
import { Conversation } from "@/lib/types";

export default function AdminConversations() {
  const [conversations, setConversations] = useState<Conversation[]>(() => getConversations());

  function resolve(id: string, status: "confirme" | "rejete") {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, hitlStatus: status } : c))
    );
  }

  return (
    <div>
      <PageHeader
        title="Conversations"
        subtitle="Echanges CONCIERGE avec les clients sur WhatsApp — confirmez les points HITL."
      />

      <div className="space-y-4">
        {conversations.map((c) => (
          <div key={c.id} className="card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-medium text-sand-900">
                  {c.clientNom} <span className="font-normal text-sand-900/50">· {c.entreprise}</span>
                </p>
                <p className="mt-0.5 text-xs text-sand-900/40">
                  {new Date(c.horodatage).toLocaleString("fr-FR")}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <LangueBadge langue={c.langue} />
                <HitlBadge status={c.hitlStatus} />
              </div>
            </div>

            <div className="mt-4 space-y-2 border-t border-sand-100 pt-4">
              <p className="text-sm">
                <span className="font-medium text-sand-900/50">Client — </span>
                <span className="text-sand-900">{c.dernierMessage}</span>
              </p>
              <p className="text-sm">
                <span className="font-medium text-sand-900/50">CONCIERGE — </span>
                <span className="text-sand-900">{c.reponse}</span>
              </p>
            </div>

            {c.hitlStatus === "en_attente" && (
              <div className="mt-4 flex gap-2 border-t border-sand-100 pt-4">
                <button
                  onClick={() => resolve(c.id, "confirme")}
                  className="btn-primary !px-3 !py-2 text-xs"
                >
                  <Check className="h-3.5 w-3.5" />
                  Confirmer
                </button>
                <button
                  onClick={() => resolve(c.id, "rejete")}
                  className="btn-secondary !px-3 !py-2 text-xs"
                >
                  <X className="h-3.5 w-3.5" />
                  Rejeter
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
