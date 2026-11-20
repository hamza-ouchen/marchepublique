"use client";

import Link from "next/link";
import { ArrowLeft, Clock, FileCheck2, Send, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageToggle } from "@/components/LanguageToggle";
import { StatCard } from "@/components/StatCard";
import { useLanguage } from "@/lib/i18n";
import { getServiceStatus } from "@/lib/api";
import { EtatCanal, EtatGlobal } from "@/lib/types";

const globalStyles: Record<EtatGlobal, string> = {
  operationnel: "bg-brand-50 text-brand-700 border-brand-200",
  degrade: "bg-amber-50 text-amber-700 border-amber-200",
  panne: "bg-red-50 text-red-700 border-red-200",
};

const channelStyles: Record<EtatCanal, string> = {
  ok: "bg-brand-50 text-brand-700",
  degrade: "bg-amber-50 text-amber-700",
  indisponible: "bg-red-50 text-red-700",
};

export default function SanteServicePage() {
  const { t, lang } = useLanguage();
  const status = getServiceStatus();

  const globalLabelKey = `status.${status.etatGlobal}`;

  return (
    <div className="min-h-screen bg-sand-50">
      <header className="mx-auto flex max-w-4xl items-center justify-between px-6 py-6">
        <Logo />
        <div className="flex items-center gap-3">
          <LanguageToggle />
          <ThemeToggle />
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-6">
        <Link href="/" className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-brand-700 hover:underline">
          <ArrowLeft className="h-4 w-4 rtl:rotate-180" />
          {t("status.backLink")}
        </Link>

        <h1 className="text-2xl font-extrabold tracking-tight text-sand-900">{t("status.title")}</h1>
        <p className="mt-1.5 text-sm text-sand-900/60">{t("status.subtitle")}</p>

        <div className={`mt-6 inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold ${globalStyles[status.etatGlobal]}`}>
          {status.etatGlobal === "operationnel" ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <AlertTriangle className="h-4 w-4" />
          )}
          {t(globalLabelKey)}
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label={t("status.lastCollect")}
            value={new Date(status.derniereCollecte).toLocaleString(lang === "ar" ? "ar-MA" : "fr-MA")}
            icon={Clock}
          />
          <StatCard
            label={t("status.offersCollected")}
            value={status.offresCollectees24h}
            icon={FileCheck2}
          />
          <StatCard
            label={t("status.digestSla")}
            value={`${status.slaDigest30j}%`}
            icon={Send}
            trend={
              status.digestLivreAvant8h
                ? `${t("status.digestOnTime")} — ${status.heureDigest}`
                : t("status.digestLate")
            }
          />
        </div>

        <div className="card mt-6 p-5">
          <h2 className="mb-3 text-sm font-semibold text-sand-900">{t("status.channels")}</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {(["whatsapp", "email", "dashboard"] as const).map((canal) => (
              <div key={canal} className="flex items-center justify-between rounded-lg bg-sand-50 px-4 py-3">
                <span className="text-sm font-medium capitalize text-sand-900">{canal}</span>
                <span className={`badge ${channelStyles[status.canaux[canal]]}`}>
                  {t(`status.channel.${status.canaux[canal]}`)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="card mt-6 p-5">
          <h2 className="mb-3 text-sm font-semibold text-sand-900">{t("status.incidents")}</h2>
          {status.incidents.length === 0 ? (
            <p className="text-sm text-sand-900/50">{t("status.noIncident")}</p>
          ) : (
            <ul className="space-y-3">
              {status.incidents.map((inc, i) => (
                <li key={i} className="flex items-start gap-3 rounded-lg bg-sand-50 p-3">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                  <div className="min-w-0">
                    <p className="text-sm text-sand-900/80">{inc.message}</p>
                    <p className="mt-1 text-xs text-sand-900/40">
                      {inc.date} {inc.resolu && `· ${t("status.resolved")}`}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
