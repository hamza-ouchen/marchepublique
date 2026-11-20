import clsx from "clsx";
import { HitlStatus } from "@/lib/types";

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
