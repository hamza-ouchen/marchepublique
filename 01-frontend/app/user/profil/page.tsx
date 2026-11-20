"use client";

import { useState } from "react";
import { Save, CheckCircle2, Info } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Field } from "@/components/Field";
import { useAuth } from "@/lib/auth-context";
import { SECTEURS, REGIONS } from "@/lib/types";

export default function UserProfil() {
  const { user, updateProfile } = useAuth();
  const [form, setForm] = useState({
    nom: user?.nom ?? "",
    entreprise: user?.entreprise ?? "",
    ice: user?.ice ?? "",
    telephone: user?.telephone ?? "",
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
    updateProfile(form);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <div className="max-w-2xl">
      <PageHeader title="Mon profil" subtitle="Vos informations chez Sou9na." />

      <div className="mb-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <p>
          Une demande de modification envoyee ici depuis WhatsApp passe par une
          confirmation humaine (HITL) avant d&apos;etre appliquee. Ici, dans le
          prototype, la sauvegarde est directe.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="card space-y-4 p-6">
        <Field label="Nom complet">
          <input className="input-field" value={form.nom} onChange={update("nom")} />
        </Field>
        <Field label="Entreprise">
          <input className="input-field" value={form.entreprise} onChange={update("entreprise")} />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="ICE">
            <input className="input-field" value={form.ice} onChange={update("ice")} />
          </Field>
          <Field label="Telephone">
            <input className="input-field" value={form.telephone} onChange={update("telephone")} />
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Secteur d'activite">
            <select
              className="input-field"
              value={form.secteurActivite}
              onChange={update("secteurActivite")}
            >
              <option value="">Selectionner...</option>
              {SECTEURS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Region">
            <select className="input-field" value={form.region} onChange={update("region")}>
              <option value="">Selectionner...</option>
              {REGIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field
          label="Qualifications / certifications"
          hint="Utile pour verifier l'eligibilite a certains appels d'offres"
        >
          <textarea
            className="input-field min-h-[80px] resize-y"
            placeholder="Ex: Qualification et classification BTP categorie 3, certificat ISO 9001..."
            value={form.qualifications}
            onChange={update("qualifications")}
          />
        </Field>

        <Field label="Email" hint="Non modifiable dans ce prototype">
          <input className="input-field opacity-60" value={user?.email ?? ""} disabled />
        </Field>

        <div className="flex items-center gap-3 pt-2">
          <button type="submit" className="btn-primary">
            <Save className="h-4 w-4" />
            Enregistrer
          </button>
          {saved && (
            <span className="flex items-center gap-1.5 text-sm text-brand-700">
              <CheckCircle2 className="h-4 w-4" />
              Enregistre
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
