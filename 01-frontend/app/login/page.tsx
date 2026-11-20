"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth, roleHome } from "@/lib/auth-context";
import { useLanguage } from "@/lib/i18n";
import { Logo } from "@/components/Logo";
import { Field } from "@/components/Field";
import { HeroIllustration } from "@/components/HeroIllustration";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageToggle } from "@/components/LanguageToggle";
import { LogIn, AlertCircle, Building2, ShieldCheck, Info } from "lucide-react";
import clsx from "clsx";

type Space = "user" | "admin";
type Step = "phone" | "code";

export default function LoginPage() {
  const { requestOtp, confirmLogin } = useAuth();
  const { t } = useLanguage();
  const router = useRouter();
  const [space, setSpace] = useState<Space>("user");
  const [step, setStep] = useState<Step>("phone");
  const [telephone, setTelephone] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const isAdminSpace = space === "admin";

  async function handleRequestCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const result = await requestOtp(telephone);
    setLoading(false);
    if (!result.ok) {
      setError(result.error ?? t("login.error.default"));
      return;
    }
    setDevCode(result.devCode ?? null);
    setStep("code");
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const result = await confirmLogin(telephone, code, space);
    setLoading(false);
    if (!result.ok) {
      setError(result.error ?? t("login.error.default"));
      return;
    }
    router.replace(roleHome(space));
  }

  return (
    <div className="flex min-h-screen">
      {/* Panneau formulaire */}
      <div className="flex w-full flex-col justify-center px-8 py-12 sm:px-16 lg:w-1/2 lg:px-24">
        <div className="mb-10 flex items-center justify-between">
          <Logo />
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight text-sand-900">
          {t("login.title")}
        </h1>
        <p className="mt-2 text-sm text-sand-900/60">
          {t("login.subtitle")}
        </p>

        <div className="mt-6 grid grid-cols-2 gap-2 rounded-xl bg-sand-100 p-1">
          <button
            type="button"
            disabled={step === "code"}
            onClick={() => {
              setSpace("user");
              setError(null);
            }}
            className={clsx(
              "flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-60",
              !isAdminSpace
                ? "bg-surface text-brand-700 shadow-sm"
                : "text-sand-900/50 hover:text-sand-900"
            )}
          >
            <Building2 className="h-4 w-4" />
            {t("common.spaceUser")}
          </button>
          <button
            type="button"
            disabled={step === "code"}
            onClick={() => {
              setSpace("admin");
              setError(null);
            }}
            className={clsx(
              "flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-60",
              isAdminSpace
                ? "bg-surface text-violet-700 shadow-sm"
                : "text-sand-900/50 hover:text-sand-900"
            )}
          >
            <ShieldCheck className="h-4 w-4" />
            {t("common.spaceAdmin")}
          </button>
        </div>

        {step === "phone" ? (
          <form onSubmit={handleRequestCode} className="mt-6 space-y-5">
            {error && (
              <div className="flex items-center gap-2 rounded-lg bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {error}
              </div>
            )}
            <Field label={t("auth.phone")} hint={t("auth.phoneHint")}>
              <input
                type="tel"
                name="login-phone"
                autoComplete="tel"
                required
                className="input-field"
                placeholder="212612345678"
                value={telephone}
                onChange={(e) => setTelephone(e.target.value)}
              />
            </Field>
            <button
              type="submit"
              disabled={loading}
              className={clsx(
                "btn-primary w-full",
                isAdminSpace && "!bg-violet-600 hover:!bg-violet-700 focus:!ring-violet-500"
              )}
            >
              <LogIn className="h-4 w-4" />
              {loading ? t("auth.sending") : t("auth.sendCode")}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerify} className="mt-6 space-y-5">
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
                name="login-code"
                autoComplete="one-time-code"
                required
                maxLength={6}
                className="input-field tracking-[0.3em]"
                placeholder="------"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </Field>
            <button
              type="submit"
              disabled={loading}
              className={clsx(
                "btn-primary w-full",
                isAdminSpace && "!bg-violet-600 hover:!bg-violet-700 focus:!ring-violet-500"
              )}
            >
              <LogIn className="h-4 w-4" />
              {loading ? t("auth.verifying") : t("auth.verify")}
            </button>
            <button
              type="button"
              onClick={() => {
                setStep("phone");
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

        <p className="mt-6 text-sm text-sand-900/60">
          {t("login.noAccount")}{" "}
          <Link href="/signup" className="font-medium text-brand-700 hover:underline">
            {t("common.signup")}
          </Link>
        </p>
      </div>

      {/* Panneau illustration */}
      <div className="relative hidden w-1/2 overflow-hidden bg-brand-900 lg:block">
        <div className="absolute inset-0 bg-gradient-to-br from-brand-700 via-brand-800 to-brand-950" />
        <div className="absolute -end-24 -top-32 h-72 w-72 rounded-full bg-brand-500/20 blur-3xl" />
        <div className="absolute -bottom-20 -start-10 h-64 w-64 rounded-full bg-brand-400/10 blur-3xl" />
        <div className="relative flex h-full flex-col justify-center px-16">
          <span className="badge badge-dot w-fit border border-white/15 bg-white/10 text-white/90">
            {t("login.panel.badge")}
          </span>
          <h2 className="mt-5 text-4xl font-extrabold leading-[1.1] tracking-tight text-white drop-shadow-sm">
            {t("login.panel.title")}
          </h2>
          <p className="mt-4 max-w-md text-white/70">
            {t("login.panel.text")}
          </p>
          <div className="mt-10 rounded-2xl border border-white/10 bg-white/[0.06] p-6 backdrop-blur-sm">
            <HeroIllustration />
          </div>
        </div>
      </div>
    </div>
  );
}
