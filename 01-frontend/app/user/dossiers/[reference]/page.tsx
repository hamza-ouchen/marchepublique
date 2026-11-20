"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Star, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { VerdictBadge, StatutBadge } from "@/components/Badge";
import { useLanguage } from "@/lib/i18n";
import { getDossier, setDossierFavori, setDossierStatut } from "@/lib/api";
import { Controle, StatutDossier } from "@/lib/types";

const controleIcon: Record<Controle, typeof CheckCircle2> = {
  ok: CheckCircle2,
  risque: AlertTriangle,
  ko: XCircle,
};

const controleColor: Record<Controle, string> = {
  ok: "text-brand-600",
  risque: "text-amber-600",
  ko: "text-red-600",
};

export default function DossierDetailPage() {
  const params = useParams<{ reference: string }>();
  const reference = decodeURIComponent(params.reference);
  const { t, lang } = useLanguage();
  const [dossier, setDossier] = useState(() => getDossier(reference));

  if (!dossier) {
    return (
      <div>
        <Link href="/user/dossiers" className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-brand-700 hover:underline">
          <ArrowLeft className="h-4 w-4 rtl:rotate-180" />
          {t("dossier.back")}
        </Link>
        <p className="card p-8 text-center text-sm text-sand-900/50">{t("dossiers.empty")}</p>
      </div>
    );
  }

  function toggleFavori() {
    if (!dossier) return;
    setDossierFavori(dossier.reference, !dossier.favori);
    setDossier({ ...dossier, favori: !dossier.favori });
  }

  function changeStatut(statut: StatutDossier) {
    if (!dossier) return;
    setDossierStatut(dossier.reference, statut);
    setDossier({ ...dossier, statut });
  }

  const controles: { key: keyof typeof dossier.controles; labelKey: string }[] = [
    { key: "cautionVsCapacite", labelKey: "controle.caution_vs_capacite" },
    { key: "iceAttestations", labelKey: "controle.ice_attestations" },
    { key: "qualifications", labelKey: "controle.qualifications" },
    { key: "delaiAtteignable", labelKey: "controle.delai_atteignable" },
  ];

  return (
    <div className="max-w-3xl">
      <Link href="/user/dossiers" className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-brand-700 hover:underline">
        <ArrowLeft className="h-4 w-4 rtl:rotate-180" />
        {t("dossier.back")}
      </Link>

      <PageHeader
        title={dossier.objet}
        subtitle={`${dossier.organisme} · ${dossier.secteur} · ${dossier.region}`}
        action={
          <button
            type="button"
            onClick={toggleFavori}
            className="btn-secondary !px-3 !py-2 text-xs"
          >
            <Star className={dossier.favori ? "h-4 w-4 fill-amber-400 text-amber-500" : "h-4 w-4"} />
            {dossier.favori ? t("dossiers.favoriRemove") : t("dossiers.favoriAdd")}
          </button>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-brand-50 text-xl font-bold text-brand-700">
          {dossier.match.total}
        </div>
        <VerdictBadge verdict={dossier.verdict} lang={lang} />
        <select
          className="input-field !w-auto"
          value={dossier.statut}
          onChange={(e) => changeStatut(e.target.value as StatutDossier)}
        >
          <option value="a_etudier">{lang === "fr" ? "A etudier" : "للدراسة"}</option>
          <option value="envoye">{lang === "fr" ? "Envoye" : "تم الإرسال"}</option>
          <option value="gagne">{lang === "fr" ? "Gagne" : "تم الفوز"}</option>
          <option value="perdu">{lang === "fr" ? "Perdu" : "خسر"}</option>
        </select>
      </div>

      <div className="card mb-6 grid grid-cols-2 gap-4 p-5 sm:grid-cols-4">
        <div>
          <p className="text-xs text-sand-900/50">{t("dossiers.amount")}</p>
          <p className="font-medium text-sand-900">{dossier.montantMad.toLocaleString("fr-MA")} MAD</p>
        </div>
        <div>
          <p className="text-xs text-sand-900/50">{t("dossier.caution")}</p>
          <p className="font-medium text-sand-900">{dossier.cautionMad.toLocaleString("fr-MA")} MAD</p>
        </div>
        <div>
          <p className="text-xs text-sand-900/50">{t("dossier.delay")}</p>
          <p className="font-medium text-sand-900">{dossier.delaiJours} j</p>
        </div>
        <div>
          <p className="text-xs text-sand-900/50">{t("dossier.remise")}</p>
          <p className="font-medium text-sand-900">{dossier.dateRemise}</p>
        </div>
      </div>

      <div className="card mb-6 p-5">
        <h2 className="mb-3 text-sm font-semibold text-sand-900">{t("dossier.scoreDetail")}</h2>
        <div className="grid grid-cols-5 gap-2 text-center text-xs">
          {Object.entries(dossier.match.composantes).map(([key, value]) => (
            <div key={key} className="rounded-lg bg-sand-50 p-2">
              <p className="font-semibold text-sand-900">{value}</p>
              <p className="text-sand-900/50">{key}</p>
            </div>
          ))}
        </div>
        {dossier.match.pointsPerdus.length > 0 && (
          <div className="mt-4">
            <p className="mb-1.5 text-xs font-medium text-sand-900/60">{t("dossier.pointsLost")}</p>
            <ul className="space-y-1 text-sm text-sand-900/70">
              {dossier.match.pointsPerdus.map((p, i) => (
                <li key={i}>· {p}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="card mb-6 p-5">
        <h2 className="mb-3 text-sm font-semibold text-sand-900">{t("dossier.controls")}</h2>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {controles.map(({ key, labelKey }) => {
            const value = dossier.controles[key];
            const Icon = controleIcon[value];
            return (
              <div key={key} className="flex items-center gap-2 rounded-lg bg-sand-50 px-3 py-2 text-sm">
                <Icon className={`h-4 w-4 shrink-0 ${controleColor[value]}`} />
                <span className="flex-1 text-sand-900/80">{t(labelKey)}</span>
                <span className={`text-xs font-medium ${controleColor[value]}`}>{t(`controle.${value}`)}</span>
              </div>
            );
          })}
        </div>
      </div>

      {dossier.risquesAVerifier.length > 0 && (
        <div className="card mb-6 p-5">
          <h2 className="mb-3 text-sm font-semibold text-sand-900">{t("dossier.risks")}</h2>
          <ul className="space-y-2 text-sm text-sand-900/70">
            {dossier.risquesAVerifier.map((r, i) => (
              <li key={i} className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="card p-5">
        <h2 className="mb-3 text-sm font-semibold text-sand-900">{t("dossier.sources")}</h2>
        <ul className="space-y-2 text-sm text-sand-900/70">
          {dossier.justifications.map((j, i) => (
            <li key={i}>
              <p>{j.constat}</p>
              <p className="text-xs text-sand-900/40">{j.reference}</p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
