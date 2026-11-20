"use client";

import { useState } from "react";
import { Search } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { getClients } from "@/lib/api";
import clsx from "clsx";

export default function AdminClients() {
  const [query, setQuery] = useState("");
  const clientsTable = getClients();

  const filtered = clientsTable.filter((c) =>
    `${c.entreprise} ${c.contact} ${c.ice}`.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div>
      <PageHeader
        title="Clients (TPME)"
        subtitle="Entreprises inscrites sur Sou9na."
        action={
          <div className="relative">
            <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-sand-900/40" />
            <input
              className="input-field w-64 ps-9"
              placeholder="Rechercher une entreprise..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        }
      />

      <div className="card overflow-hidden">
        <table className="w-full text-start text-sm">
          <thead>
            <tr className="border-b border-sand-200 text-xs uppercase tracking-wide text-sand-900/40">
              <th className="px-6 py-3 font-medium">Entreprise</th>
              <th className="px-6 py-3 font-medium">ICE</th>
              <th className="px-6 py-3 font-medium">Contact</th>
              <th className="px-6 py-3 font-medium">Secteur</th>
              <th className="px-6 py-3 font-medium">Region</th>
              <th className="px-6 py-3 font-medium">Statut</th>
              <th className="px-6 py-3 font-medium">Client depuis</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <tr key={c.id} className="border-b border-sand-100 last:border-0">
                <td className="px-6 py-3.5 font-medium text-sand-900">{c.entreprise}</td>
                <td className="px-6 py-3.5 text-sand-900/60">{c.ice}</td>
                <td className="px-6 py-3.5 text-sand-900/60">{c.contact}</td>
                <td className="px-6 py-3.5 text-sand-900/60">{c.secteur}</td>
                <td className="px-6 py-3.5 text-sand-900/60">{c.region}</td>
                <td className="px-6 py-3.5">
                  <span
                    className={clsx(
                      "badge",
                      c.statut === "Actif"
                        ? "bg-brand-50 text-brand-700"
                        : "bg-amber-50 text-amber-700"
                    )}
                  >
                    {c.statut}
                  </span>
                </td>
                <td className="px-6 py-3.5 text-sand-900/60">{c.depuis}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center text-sand-900/50">
                  Aucun resultat.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
