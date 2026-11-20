"use client";

import { MessageSquare, Users2, Clock, CheckCircle2 } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";
import { HitlBadge, LangueBadge } from "@/components/Badge";
import { getConversations, getWeeklyVolume, getClients } from "@/lib/api";

export default function AdminDashboard() {
  const mockConversations = getConversations();
  const weeklyVolume = getWeeklyVolume();
  const clientsTable = getClients();
  const enAttente = mockConversations.filter((c) => c.hitlStatus === "en_attente").length;
  const maxVolume = Math.max(...weeklyVolume.map((d) => d.value));

  return (
    <div>
      <PageHeader
        title="Tableau de bord"
        subtitle="Vue d'ensemble de l'activite CONCIERGE sur WhatsApp."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Conversations (7j)" value={weeklyVolume.reduce((a, b) => a + b.value, 0)} icon={MessageSquare} trend="+12% vs semaine derniere" />
        <StatCard label="Clients actifs" value={clientsTable.filter((c) => c.statut === "Actif").length} icon={Users2} />
        <StatCard label="HITL en attente" value={enAttente} icon={Clock} />
        <StatCard label="Taux de reponse" value="100%" icon={CheckCircle2} trend="Aucun message sans reponse" />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-5">
        <div className="card p-6 lg:col-span-3">
          <h2 className="text-sm font-semibold text-sand-900">Volume de conversations (7 derniers jours)</h2>
          <div className="mt-6 flex items-end gap-3" style={{ height: 160 }}>
            {weeklyVolume.map((d) => (
              <div key={d.label} className="flex flex-1 flex-col items-center gap-2">
                <div
                  className="w-full rounded-t-md bg-brand-500/90 transition-all"
                  style={{ height: `${(d.value / maxVolume) * 120}px` }}
                  title={`${d.value} conversations`}
                />
                <span className="text-xs text-sand-900/50">{d.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-6 lg:col-span-2">
          <h2 className="text-sm font-semibold text-sand-900">Points HITL en attente</h2>
          <ul className="mt-4 space-y-3">
            {mockConversations
              .filter((c) => c.hitlStatus === "en_attente")
              .map((c) => (
                <li key={c.id} className="flex items-start justify-between gap-3 rounded-lg border border-sand-200 p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-sand-900">{c.clientNom}</p>
                    <p className="truncate text-xs text-sand-900/50">{c.entreprise}</p>
                  </div>
                  <LangueBadge langue={c.langue} />
                </li>
              ))}
            {enAttente === 0 && (
              <p className="text-sm text-sand-900/50">Aucun point en attente.</p>
            )}
          </ul>
        </div>
      </div>

      <div className="card mt-6 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4">
          <h2 className="text-sm font-semibold text-sand-900">Conversations recentes</h2>
        </div>
        <table className="w-full text-start text-sm">
          <thead>
            <tr className="border-y border-sand-200 text-xs uppercase tracking-wide text-sand-900/40">
              <th className="px-6 py-3 font-medium">Client</th>
              <th className="px-6 py-3 font-medium">Message</th>
              <th className="px-6 py-3 font-medium">Langue</th>
              <th className="px-6 py-3 font-medium">HITL</th>
            </tr>
          </thead>
          <tbody>
            {mockConversations.map((c) => (
              <tr key={c.id} className="border-b border-sand-100 last:border-0">
                <td className="px-6 py-3.5">
                  <p className="font-medium text-sand-900">{c.clientNom}</p>
                  <p className="text-xs text-sand-900/50">{c.entreprise}</p>
                </td>
                <td className="max-w-xs truncate px-6 py-3.5 text-sand-900/70">
                  {c.dernierMessage}
                </td>
                <td className="px-6 py-3.5">
                  <LangueBadge langue={c.langue} />
                </td>
                <td className="px-6 py-3.5">
                  <HitlBadge status={c.hitlStatus} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
