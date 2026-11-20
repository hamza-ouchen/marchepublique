"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useLanguage } from "@/lib/i18n";
import { Logo } from "@/components/Logo";
import { Field } from "@/components/Field";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageToggle } from "@/components/LanguageToggle";
import { SECTEURS, REGIONS } from "@/lib/types";
import { UserPlus, AlertCircle, Info } from "lucide-react";

type Step = "profile" | "code";

export default function SignupPage() {
  const { requestOtp, confirmSignup } = useAuth();
  const { t } = useLanguage();
  const router = useRouter();
  const [step, setStep] = useState<Step>("profile");
  const [form, setForm] = useState({
    nom: "",
    entreprise: "",
    ice: "",
    telephone: "",
    email: "",
    secteurActivite: "",
    region: "",
    qualifications: "",
  });
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function update(key: keyof typeof form) {
    return (
      e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
    ) => setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  async function handleRequestCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const result = await requestOtp(form.telephone);
    setLoading(false);
    if (!result.ok) {
      setError(result.error ?? "Erreur lors de la demande de code.");
      return;
    }
    setDevCode(result.devCode ?? null);
    setStep("code");
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const result = await confirmSignup(form.telephone, code, {
      nom: form.nom,
      telephone: form.telephone,
      entreprise: form.entreprise,
      email: form.email || undefined,
      ice: form.ice || undefined,
      secteurActivite: form.secteurActivite || undefined,
      region: form.region || undefined,
      qualifications: form.qualifications || undefined,
    });
    setLoading(false);
    if (!result.ok) {
      setError(result.error ?? "Erreur lors de la creation du compte.");
      return;
    }
    router.replace("/user");
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-sand-50 px-6 py-12">
      <div className="absolute end-6 top-6 flex items-center gap-2">
        <LanguageToggle />
        <ThemeToggle />
      </div>
      <div className="w-full max-w-lg">
        <Logo className="mb-8 justify-center" />
        <div className="card p-8 sm:p-10">
          <span className="badge badge-dot border border-brand-100 bg-brand-50 text-brand-700">
            {t("signup.badge")}
          </span>
          <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-sand-900">
            {t("signup.title")}
          </h1>
          <p className="mt-1.5 text-sm text-sand-900/60">
            {t("signup.subtitle")}
          </p>

          {step === "profile" ? (
            <form onSubmit={handleRequestCode} autoComplete="off" className="mt-6 space-y-4">
              {error && (
                <div className="flex items-center gap-2 rounded-lg bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {error}
                </div>
              )}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label={t("signup.fullName")}>
                  <input
                    required
                    className="input-field"
                    placeholder="Youssef Amrani"
                    value={form.nom}
                    onChange={update("nom")}
                  />
                </Field>
                <Field label={t("auth.phone")} hint={t("auth.phoneHint")}>
                  <input
                    type="tel"
                    required
                    className="input-field"
                    placeholder="212612345678"
                    value={form.telephone}
                    onChange={update("telephone")}
                  />
                </Field>
              </div>
              <Field label={t("signup.company")}>
                <input
                  required
                  className="input-field"
                  placeholder="Amrani Travaux SARL"
                  value={form.entreprise}
                  onChange={update("entreprise")}
                />
              </Field>
              <Field label="ICE" hint={t("signup.iceHint")}>
                <input
                  className="input-field"
                  placeholder="0012345678"
                  value={form.ice}
                  onChange={update("ice")}
                />
              </Field>

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
                  <select
                    className="input-field"
                    value={form.region}
                    onChange={update("region")}
                  >
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

              <Field label={`${t("common.email")} (optionnel)`}>
                <input
                  type="email"
                  name="signup-email"
                  autoComplete="off"
                  className="input-field"
                  placeholder="vous@entreprise.ma"
                  value={form.email}
                  onChange={update("email")}
                />
              </Field>
              <button type="submit" disabled={loading} className="btn-primary w-full">
                <UserPlus className="h-4 w-4" />
                {loading ? t("auth.sending") : t("auth.sendCode")}
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerify} className="mt-6 space-y-4">
              {error && (
                <div className="flex items-center gap-2 rounded-lg bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {error}
                </div>
              )}
              {devCode && (
                <div className="flex items-center gap-2 rounded-lg bg-amber-50 px-3.5 py-2.5 text-sm text-amber-700">
                  <Info className="h-4 w-4 shrink-0" />
                  {t("auth.testMode")} <span className="font-mono font-semibold">{devCode}</span>
                </div>
              )}
              <p className="text-sm text-sand-900/60">{t("auth.codeSentTo")}</p>
              <Field label={t("auth.enterCode")}>
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  required
                  maxLength={6}
                  className="input-field tracking-[0.3em]"
                  placeholder="------"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </Field>
              <button type="submit" disabled={loading} className="btn-primary w-full">
                <UserPlus className="h-4 w-4" />
                {loading ? t("auth.verifying") : t("signup.submit")}
              </button>
              <button
                type="button"
                onClick={() => {
                  setStep("profile");
                  setCode("");
                  setDevCode(null);
                  setError(null);
                }}
                className="w-full text-center text-sm font-medium text-brand-700 hover:underline"
              >
                {t("auth.changeNumber")}
              </button>
            </form>
          )}

          <p className="mt-6 text-center text-sm text-sand-900/60">
            {t("signup.alreadyRegistered")}{" "}
            <Link href="/login" className="font-medium text-brand-700 hover:underline">
              {t("common.login")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
