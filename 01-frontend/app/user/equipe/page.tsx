"use client";

import { useState } from "react";
import { UserPlus, Trash2, Info } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Field } from "@/components/Field";
import { useLanguage } from "@/lib/i18n";
import { getTeamMembers, addTeamMember, removeTeamMember } from "@/lib/api";
import { PLAN_499_SEAT_LIMIT } from "@/lib/mock-data";

export default function EquipePage() {
  const { t } = useLanguage();
  const [members, setMembers] = useState(() => getTeamMembers());
  const [nom, setNom] = useState("");
  const [telephone, setTelephone] = useState("");
  const [error, setError] = useState<string | null>(null);

  const atLimit = members.length >= PLAN_499_SEAT_LIMIT;

  function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (atLimit) {
      setError(t("team.seatLimitReached"));
      return;
    }
    const result = addTeamMember(nom, telephone);
    if (!result.ok) {
      setError(result.error ?? null);
      return;
    }
    setMembers(getTeamMembers());
    setNom("");
    setTelephone("");
  }

  function handleRemove(id: string) {
    removeTeamMember(id);
    setMembers(getTeamMembers());
  }

  return (
    <div className="max-w-2xl">
      <PageHeader title={t("team.title")} subtitle={t("team.subtitle")} />

      <div className="mb-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <p>{t("team.placeholderNotice")}</p>
      </div>

      <div className="card mb-6 p-5">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-medium text-sand-900">
            {members.length} / {PLAN_499_SEAT_LIMIT} {t("team.seatsUsed")}
          </p>
        </div>
        <ul className="space-y-2">
          {members.map((m) => (
            <li key={m.id} className="flex items-center justify-between gap-3 rounded-lg border border-sand-200 p-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-sand-900">{m.nom}</p>
                <p className="truncate text-xs text-sand-900/50">{m.telephone}</p>
              </div>
              <span className="badge bg-sand-100 text-sand-900/70">
                {m.role === "titulaire" ? t("team.role.titulaire") : t("team.role.membre")}
              </span>
              {m.role !== "titulaire" && (
                <button
                  type="button"
                  onClick={() => handleRemove(m.id)}
                  aria-label={t("team.remove")}
                  title={t("team.remove")}
                  className="shrink-0 text-sand-900/40 transition-colors hover:text-red-600"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="card p-5">
        <h2 className="mb-3 text-sm font-semibold text-sand-900">{t("team.inviteTitle")}</h2>
        <form onSubmit={handleInvite} className="space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label={t("team.memberName")}>
              <input
                required
                className="input-field"
                value={nom}
                onChange={(e) => setNom(e.target.value)}
              />
            </Field>
            <Field label={t("auth.phone")} hint={t("auth.phoneHint")}>
              <input
                type="tel"
                required
                className="input-field"
                placeholder="212612345678"
                value={telephone}
                onChange={(e) => setTelephone(e.target.value)}
              />
            </Field>
          </div>
          <button type="submit" disabled={atLimit} className="btn-primary w-full disabled:cursor-not-allowed disabled:opacity-50">
            <UserPlus className="h-4 w-4" />
            {t("team.invite")}
          </button>
        </form>
      </div>
    </div>
  );
}
