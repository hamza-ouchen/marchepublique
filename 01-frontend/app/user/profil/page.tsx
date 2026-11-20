"use client";

import { useState } from "react";
import { Save, CheckCircle2, Info } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Field } from "@/components/Field";
import { useAuth } from "@/lib/auth-context";
import { useLanguage } from "@/lib/i18n";
import { SECTEURS, REGIONS } from "@/lib/types";

export default function UserProfil() {
  const { user, updateProfile } = useAuth();
  const { t } = useLanguage();
  const [form, setForm] = useState({
    nom: user?.nom ?? "",
    entreprise: user?.entreprise ?? "",
    ice: user?.ice ?? "",
    secteurActivite: user?.secteurActivite ?? "",
    region: user?.region ?? "",
    qualifications: user?.qualifications ?? "",
  });
  const [saved, setSaved] = useState(false);

  function update(key: keyof typeof form) {
    return (
      e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
    ) => setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    // Le numero WhatsApp (identifiant de connexion) n'est jamais inclus ici —
    // il ne se change pas depuis le profil, seulement via une nouvelle
    // verification OTP cote backend.
    updateProfile(form);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <div className="max-w-2xl">
      <PageHeader title={t("profile.title")} subtitle={t("profile.subtitle")} />

      <div className="mb-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <p>{t("profile.hitlNotice")}</p>
      </div>

      <form onSubmit={handleSubmit} className="card space-y-4 p-6">
        <Field label={t("signup.fullName")}>
          <input className="input-field" value={form.nom} onChange={update("nom")} />
        </Field>
        <Field label={t("signup.company")}>
          <input className="input-field" value={form.entreprise} onChange={update("entreprise")} />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="ICE">
            <input className="input-field" value={form.ice} onChange={update("ice")} />
          </Field>
          <Field label={t("auth.phone")} hint={t("profile.notEditable")}>
            <input className="input-field opacity-60" value={user?.telephone ?? ""} disabled />
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t("signup.sector")}>
            <select
              className="input-field"
              value={form.secteurActivite}
              onChange={update("secteurActivite")}
            >
              <option value="">{t("common.select")}</option>
              {SECTEURS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("signup.region")}>
            <select className="input-field" value={form.region} onChange={update("region")}>
              <option value="">{t("common.select")}</option>
              {REGIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field
          label={t("signup.qualifications")}
          hint={t("signup.qualificationsHint")}
        >
          <textarea
            className="input-field min-h-[80px] resize-y"
            placeholder="Ex: Qualification et classification BTP categorie 3, certificat ISO 9001..."
            value={form.qualifications}
            onChange={update("qualifications")}
          />
        </Field>

        {user?.email && (
          <Field label={`${t("common.email")} (${t("profile.notEditable")})`}>
            <input className="input-field opacity-60" value={user.email} disabled />
          </Field>
        )}

        <div className="flex items-center gap-3 pt-2">
          <button type="submit" className="btn-primary">
            <Save className="h-4 w-4" />
            {t("profile.save")}
          </button>
          {saved && (
            <span className="flex items-center gap-1.5 text-sm text-brand-700">
              <CheckCircle2 className="h-4 w-4" />
              {t("profile.saved")}
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
