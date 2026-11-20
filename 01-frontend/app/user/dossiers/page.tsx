"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Star, ArrowRight } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { VerdictBadge } from "@/components/Badge";
import { useLanguage } from "@/lib/i18n";
import { getDossiers, setDossierFavori } from "@/lib/api";
import { SECTEURS, REGIONS, Verdict } from "@/lib/types";

export default function DossiersPage() {
  const { t, lang } = useLanguage();
  const [dossiers, setDossiers] = useState(() => getDossiers());
  const [secteur, setSecteur] = useState("");
  const [region, setRegion] = useState("");
  const [verdict, setVerdict] = useState<Verdict | "">("");
  const [montantMin, setMontantMin] = useState("");
  const [favorisOnly, setFavorisOnly] = useState(false);

  const filtered = useMemo(() => {
    return dossiers
      .filter((d) => (secteur ? d.secteur === secteur : true))
      .filter((d) => (region ? d.region === region : true))
      .filter((d) => (verdict ? d.verdict === verdict : true))
      .filter((d) => (montantMin ? d.montantMad >= Number(montantMin) : true))
      .filter((d) => (favorisOnly ? d.favori : true))
      .sort((a, b) => b.match.total - a.match.total);
  }, [dossiers, secteur, region, verdict, montantMin, favorisOnly]);

  function toggleFavori(reference: string, current: boolean) {
    setDossierFavori(reference, !current);
    setDossiers((prev) =>
      prev.map((d) => (d.reference === reference ? { ...d, favori: !current } : d))
    );
  }

  return (
    <div>
      <PageHeader title={t("dossiers.title")} subtitle={t("dossiers.subtitle")} />

      <div className="card mb-6 grid grid-cols-1 gap-4 p-4 sm:grid-cols-4">
        <select className="input-field" value={secteur} onChange={(e) => setSecteur(e.target.value)}>
          <option value="">{`${t("dossiers.filter.sector")} — ${t("dossiers.filter.all")}`}</option>
          {SECTEURS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select className="input-field" value={region} onChange={(e) => setRegion(e.target.value)}>
          <option value="">{`${t("dossiers.filter.region")} — ${t("dossiers.filter.all")}`}</option>
          {REGIONS.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        <select
          className="input-field"
          value={verdict}
          onChange={(e) => setVerdict(e.target.value as Verdict | "")}
        >
          <option value="">{`${t("dossiers.filter.verdict")} — ${t("dossiers.filter.all")}`}</option>
          <option value="GO">GO</option>
          <option value="A_ETUDIER">{lang === "fr" ? "A etudier" : "للدراسة"}</option>
          <option value="NO_GO">NO-GO</option>
        </select>
        <input
          type="number"
          min={0}
          className="input-field"
          placeholder={t("dossiers.filter.minAmount")}
          value={montantMin}
          onChange={(e) => setMontantMin(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm text-sand-900/70 sm:col-span-4">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-sand-300 text-brand-600 focus:ring-brand-500"
            checked={favorisOnly}
            onChange={(e) => setFavorisOnly(e.target.checked)}
          />
          {t("dossiers.favorisOnly")}
        </label>
      </div>

      <div className="space-y-3">
        {filtered.map((d) => (
          <div key={d.reference} className="card flex items-center gap-4 p-4">
            <button
              type="button"
              onClick={() => toggleFavori(d.reference, d.favori)}
              aria-label={d.favori ? t("dossiers.favoriRemove") : t("dossiers.favoriAdd")}
              title={d.favori ? t("dossiers.favoriRemove") : t("dossiers.favoriAdd")}
              className="shrink-0 text-sand-900/30 transition-colors hover:text-amber-500"
            >
              <Star className={d.favori ? "h-5 w-5 fill-amber-400 text-amber-500" : "h-5 w-5"} />
            </button>

            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-base font-bold text-brand-700">
              {d.match.total}
            </div>

            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-sand-900">{d.objet}</p>
              <p className="truncate text-xs text-sand-900/50">
                {d.organisme} · {d.secteur} · {d.region}
              </p>
            </div>

            <div className="hidden text-right text-xs text-sand-900/50 sm:block">
              <p>{t("dossiers.amount")}: {d.montantMad.toLocaleString("fr-MA")} MAD</p>
              <p>{t("dossiers.deadline")}: {d.dateRemise}</p>
            </div>

            <VerdictBadge verdict={d.verdict} lang={lang} />

            <Link
              href={`/user/dossiers/${encodeURIComponent(d.reference)}`}
              className="btn-secondary !px-3 !py-2 text-xs"
            >
              {t("dossiers.viewDetail")}
              <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
            </Link>
          </div>
        ))}
        {filtered.length === 0 && (
          <p className="card p-8 text-center text-sm text-sand-900/50">{t("dossiers.empty")}</p>
        )}
      </div>
    </div>
  );
}
