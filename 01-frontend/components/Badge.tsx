import clsx from "clsx";
import { HitlStatus, Verdict, StatutDossier } from "@/lib/types";

const hitlStyles: Record<HitlStatus, string> = {
  en_attente: "bg-amber-50 text-amber-700",
  confirme: "bg-brand-50 text-brand-700",
  rejete: "bg-red-50 text-red-700",
  non_requis: "bg-sand-100 text-sand-900/60",
};

const hitlLabels: Record<HitlStatus, string> = {
  en_attente: "En attente",
  confirme: "Confirme",
  rejete: "Rejete",
  non_requis: "Non requis",
};

export function HitlBadge({ status }: { status: HitlStatus }) {
  return (
    <span className={clsx("badge", hitlStyles[status])}>
      {hitlLabels[status]}
    </span>
  );
}

const langueLabels: Record<string, string> = {
  fr: "FR",
  ar: "AR",
  darija: "Darija",
};

export function LangueBadge({ langue }: { langue: string }) {
  return (
    <span className="badge bg-sand-100 text-sand-900/70">
      {langueLabels[langue] ?? langue}
    </span>
  );
}

const verdictStyles: Record<Verdict, string> = {
  GO: "bg-brand-50 text-brand-700",
  A_ETUDIER: "bg-amber-50 text-amber-700",
  NO_GO: "bg-red-50 text-red-700",
};

const verdictLabels: Record<Verdict, { fr: string; ar: string }> = {
  GO: { fr: "GO", ar: "موافق" },
  A_ETUDIER: { fr: "A etudier", ar: "للدراسة" },
  NO_GO: { fr: "NO-GO", ar: "مرفوض" },
};

export function VerdictBadge({ verdict, lang }: { verdict: Verdict; lang: "fr" | "ar" }) {
  return (
    <span className={clsx("badge", verdictStyles[verdict])}>
      {verdictLabels[verdict][lang]}
    </span>
  );
}

const statutStyles: Record<StatutDossier, string> = {
  a_etudier: "bg-sand-100 text-sand-900/70",
  envoye: "bg-violet-50 text-violet-700",
  gagne: "bg-brand-50 text-brand-700",
  perdu: "bg-red-50 text-red-700",
};

const statutLabels: Record<StatutDossier, { fr: string; ar: string }> = {
  a_etudier: { fr: "A etudier", ar: "للدراسة" },
  envoye: { fr: "Envoye", ar: "تم الإرسال" },
  gagne: { fr: "Gagne", ar: "تم الفوز" },
  perdu: { fr: "Perdu", ar: "خسر" },
};

export function StatutBadge({ statut, lang }: { statut: StatutDossier; lang: "fr" | "ar" }) {
  return (
    <span className={clsx("badge", statutStyles[statut])}>
      {statutLabels[statut][lang]}
    </span>
  );
}
