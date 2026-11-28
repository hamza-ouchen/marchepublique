"use client";

// Page dédiée à une opportunité documentée : dossier complet, recommandations,
// points à vérifier, conseils, preuves et rapport PDF téléchargeable.

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { getAuth } from "@/app/lib";
import BrandLoader from "@/app/brand-loader";
import type { OpportunityDetail } from "@/lib/types";

function fmtDate(value: string | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("fr-MA", {
        day: "2-digit",
        month: "long",
        year: "numeric",
      }).format(date);
}

function fmtMoney(value: number | null): string {
  if (value === null || value === undefined) return "Non renseigné";
  return new Intl.NumberFormat("fr-MA", {
    style: "currency",
    currency: "MAD",
    maximumFractionDigits: 0,
  }).format(value);
}

export default function OfferDetailPage() {
  const [detail, setDetail] = useState<OpportunityDetail | null>(null);
  const [error, setError] = useState("");
  const [reference, setReference] = useState("");

  useEffect(() => {
    const auth = getAuth();
    if (!auth) {
      window.location.href = "/login";
      return;
    }
    const ref = new URLSearchParams(window.location.search).get("reference") || "";
    setReference(ref);
    if (!ref) {
      setError("Référence d'offre manquante.");
      return;
    }
    api.opportunityDetail(ref)
      .then(setDetail)
      .catch((exc: Error) => setError(exc.message || "Dossier indisponible"));
  }, []);

  if (!reference && !error) {
    return <BrandLoader label="Ouverture du dossier…" />;
  }
  if (!detail && !error) {
    return <BrandLoader label="Préparation du dossier documenté…" />;
  }
  if (error || !detail) {
    return (
      <main className="min-h-screen bg-paper text-ink flex items-center justify-center p-6">
        <div className="max-w-lg w-full bg-white border border-line rounded-2xl p-8 text-center space-y-3">
          <span className="text-3xl">!</span>
          <h1 className="font-display text-xl font-bold">Dossier indisponible</h1>
          <p className="text-xs text-muted">{error}</p>
          <Link href="/dashboard" className="inline-block bg-greenbrand text-white px-4 py-2 rounded text-xs font-bold">
            Retour au tableau de bord
          </Link>
        </div>
      </main>
    );
  }

  const o = detail.opportunity;
  const a = detail.analysis;
  const verdictCls = o.verdict === "go"
    ? "bg-greenbg text-greenbrand"
    : o.verdict === "nogo"
      ? "bg-red-50 text-redbrand"
      : "bg-amberbg text-amberbrand";
  const verdictLabel = o.verdict === "go" ? "GO" : o.verdict === "nogo" ? "NO_GO" : "À étudier";

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="bg-white border-b border-line">
        <div className="max-w-[1100px] mx-auto px-4 lg:px-8 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="font-display text-lg font-bold text-greenbrand">Sou9na</span>
            <span className="text-xs text-muted">Dossier d&apos;opportunité</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void api.downloadReport(reference)}
              className="bg-greenbrand hover:bg-[#18553f] text-white px-4 py-2 rounded text-xs font-bold"
            >
              Télécharger le rapport PDF
            </button>
            <Link href="/dashboard" className="border border-line px-4 py-2 rounded text-xs font-bold hover:bg-paper">
              Retour
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-[1100px] mx-auto px-4 lg:px-8 py-8 space-y-6">
        <section className="bg-white border border-line rounded-2xl p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2 max-w-3xl">
              <span className="text-[10px] uppercase font-bold tracking-wider text-terra">
                {o.source_ref}
              </span>
              <h1 className="font-display text-2xl lg:text-3xl font-bold leading-tight">
                {o.title.fr}
              </h1>
              <p className="text-sm text-muted">{o.buyer.fr}</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-center">
                <span className="block font-display text-3xl font-bold text-greenbrand">{o.match_score}</span>
                <span className="text-[9px] uppercase font-bold text-muted">Match /100</span>
              </div>
              <span className={`px-3 py-1 rounded font-bold text-xs ${verdictCls}`}>{verdictLabel}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
            {[
              ["Échéance", fmtDate(o.deadline)],
              ["Localisation", o.city],
              ["Montant", fmtMoney(o.amount)],
              ["Caution", fmtMoney(o.guarantee)],
            ].map(([label, value]) => (
              <div key={label} className="bg-paper border border-line rounded p-3">
                <span className="block text-[10px] text-muted uppercase font-bold">{label}</span>
                <strong className="text-xs text-ink">{value}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-white border border-line rounded-2xl p-6 space-y-2">
          <h2 className="font-display text-lg font-bold">Résumé exécutif</h2>
          <p className="text-sm text-ink leading-relaxed">{a.summary}</p>
          <p className="text-[11px] text-muted">
            Analyse calculée à partir des seules offres disposant de documents ou de sections CPS.
          </p>
        </section>

        <div className="grid lg:grid-cols-2 gap-6">
          <section className="bg-white border border-line rounded-2xl p-6 space-y-3">
            <h2 className="font-display text-lg font-bold">Recommandations</h2>
            <ol className="space-y-2">
              {a.recommendations.map((rec, i) => (
                <li key={i} className="flex gap-3 text-xs text-ink">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-greenbrand/10 text-[10px] font-bold text-greenbrand">
                    {i + 1}
                  </span>
                  <span className="leading-relaxed">{rec}</span>
                </li>
              ))}
            </ol>
          </section>

          <section className="bg-white border border-line rounded-2xl p-6 space-y-3">
            <h2 className="font-display text-lg font-bold">Conseil Sou9na</h2>
            <p className="text-xs text-ink leading-relaxed">{a.advice}</p>
            <div className="bg-greenbg/60 border border-greenbrand/20 rounded p-3 text-[11px] text-muted">
              Ce conseil est indicatif. Il ne remplace pas la lecture du dossier de consultation officiel.
            </div>
          </section>
        </div>

        <section className="bg-white border border-line rounded-2xl p-6 space-y-3">
          <h2 className="font-display text-lg font-bold">Points à vérifier dans le dossier officiel</h2>
          <p className="text-[11px] text-muted">
            Actions de vérification déduites du dossier. Sou9na n&apos;affirme aucune pénalité ni retard
            non mentionné dans les pièces analysées.
          </p>
          {a.points_to_verify.length === 0 ? (
            <p className="text-xs text-muted">Aucun point bloquant identifié.</p>
          ) : (
            <ul className="space-y-2">
              {a.points_to_verify.map((point, i) => (
                <li key={i} className="flex gap-2 text-xs text-ink bg-paper/60 border border-line rounded p-2">
                  <span className="text-amberbrand font-bold">!</span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-white border border-line rounded-2xl p-6 space-y-3">
          <h2 className="font-display text-lg font-bold">Justifications et preuves</h2>
          {a.evidence.length === 0 ? (
            <p className="text-xs text-muted">Aucune justification structurée enregistrée.</p>
          ) : (
            <ul className="space-y-2">
              {a.evidence.map((item, i) => (
                <li key={i} className="text-xs text-ink border-b border-line/60 pb-2">
                  <strong className="font-semibold">{item.constat || "—"}</strong>
                  {item.reference && <span className="block text-muted">{item.reference}</span>}
                  {item.pages && <span className="block text-muted">Pages : {item.pages}</span>}
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="grid lg:grid-cols-2 gap-6">
          <section className="bg-white border border-line rounded-2xl p-6 space-y-3">
            <h2 className="font-display text-lg font-bold">Documents du dossier</h2>
            {detail.documents.length === 0 ? (
              <p className="text-xs text-muted">Aucun document texte exploitable.</p>
            ) : (
              detail.documents.map((doc, i) => (
                <div key={i} className="border border-line rounded p-3 space-y-1">
                  <span className="block text-xs font-bold text-ink">{doc.filename}</span>
                  <span className="block text-[10px] text-muted">
                    {doc.doc_type} · {doc.char_count} caractères · {doc.sections} sections
                  </span>
                  {doc.excerpt && <p className="text-[11px] text-muted line-clamp-3">{doc.excerpt}</p>}
                </div>
              ))
            )}
          </section>

          <section className="bg-white border border-line rounded-2xl p-6 space-y-3">
            <h2 className="font-display text-lg font-bold">Sections CPS</h2>
            {detail.sections.length === 0 ? (
              <p className="text-xs text-muted">Aucune section CPS structurée.</p>
            ) : (
              detail.sections.slice(0, 12).map((sec, i) => (
                <div key={i} className="border border-line rounded p-3 space-y-1">
                  <span className="block text-xs font-bold text-ink">
                    {sec.numero} {sec.titre}
                  </span>
                  <span className="block text-[10px] text-muted">
                    {sec.filename}{sec.pages ? ` · p. ${sec.pages}` : ""}
                  </span>
                  {sec.texte && <p className="text-[11px] text-muted line-clamp-3">{sec.texte}</p>}
                </div>
              ))
            )}
          </section>
        </div>

        {o.url && (
          <section className="bg-white border border-line rounded-2xl p-6">
            <h2 className="font-display text-lg font-bold mb-2">Source officielle</h2>
            <a href={o.url} target="_blank" rel="noreferrer" className="text-greenbrand underline text-xs">
              Ouvrir l&apos;avis sur le portail officiel ↗
            </a>
          </section>
        )}
      </main>
    </div>
  );
}
