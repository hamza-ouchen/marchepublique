"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth, roleHome } from "@/lib/auth-context";
import { Logo } from "@/components/Logo";
import { Field } from "@/components/Field";
import { HeroIllustration } from "@/components/HeroIllustration";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LogIn, AlertCircle, Building2, ShieldCheck } from "lucide-react";
import clsx from "clsx";

type Space = "user" | "admin";

export default function LoginPage() {
  const { login, logout } = useAuth();
  const router = useRouter();
  const [space, setSpace] = useState<Space>("user");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const isAdminSpace = space === "admin";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const result = login(email, password);
    setLoading(false);
    if (!result.ok) {
      setError(result.error ?? "Erreur de connexion.");
      return;
    }
    const raw = window.localStorage.getItem("sou9na_session");
    const connectedUser = raw ? JSON.parse(raw) : null;
    if (!connectedUser) {
      setError("Erreur de connexion.");
      return;
    }
    if (connectedUser.role !== space) {
      logout();
      setError(
        isAdminSpace
          ? "Ce compte n'est pas un compte Admin. Choisissez l'espace TPME."
          : "Ce compte est un compte Admin. Choisissez l'espace Admin."
      );
      return;
    }
    router.replace(roleHome(connectedUser.role));
  }

  return (
    <div className="flex min-h-screen">
      {/* Panneau gauche — formulaire */}
      <div className="flex w-full flex-col justify-center px-8 py-12 sm:px-16 lg:w-1/2 lg:px-24">
        <div className="mb-10 flex items-center justify-between">
          <Logo />
          <ThemeToggle />
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight text-sand-900">
          Connexion
        </h1>
        <p className="mt-2 text-sm text-sand-900/60">
          Choisissez votre espace puis connectez-vous.
        </p>

        <div className="mt-6 grid grid-cols-2 gap-2 rounded-xl bg-sand-100 p-1">
          <button
            type="button"
            onClick={() => {
              setSpace("user");
              setError(null);
            }}
            className={clsx(
              "flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-semibold transition-all",
              !isAdminSpace
                ? "bg-surface text-brand-700 shadow-sm"
                : "text-sand-900/50 hover:text-sand-900"
            )}
          >
            <Building2 className="h-4 w-4" />
            Espace TPME
          </button>
          <button
            type="button"
            onClick={() => {
              setSpace("admin");
              setError(null);
            }}
            className={clsx(
              "flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-semibold transition-all",
              isAdminSpace
                ? "bg-surface text-violet-700 shadow-sm"
                : "text-sand-900/50 hover:text-sand-900"
            )}
          >
            <ShieldCheck className="h-4 w-4" />
            Espace Admin
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          {error && (
            <div className="flex items-center gap-2 rounded-lg bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}
          <Field label="Email">
            <input
              type="email"
              name="login-email"
              autoComplete="email"
              required
              className="input-field"
              placeholder="vous@entreprise.ma"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <Field label="Mot de passe">
            <input
              type="password"
              name="login-password"
              autoComplete="current-password"
              required
              className="input-field"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
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
            Se connecter
          </button>
        </form>

        <p className="mt-6 text-sm text-sand-900/60">
          Pas encore de compte ?{" "}
          <Link href="/signup" className="font-medium text-brand-700 hover:underline">
            Creer un compte
          </Link>
        </p>
      </div>

      {/* Panneau droit — illustration */}
      <div className="relative hidden w-1/2 overflow-hidden bg-brand-900 lg:block">
        <div className="absolute inset-0 bg-gradient-to-br from-brand-700 via-brand-800 to-brand-950" />
        <div className="absolute -right-24 -top-32 h-72 w-72 rounded-full bg-brand-500/20 blur-3xl" />
        <div className="absolute -bottom-20 -left-10 h-64 w-64 rounded-full bg-brand-400/10 blur-3xl" />
        <div className="relative flex h-full flex-col justify-center px-16">
          <span className="badge badge-dot w-fit border border-white/15 bg-white/10 text-white/90">
            Plateforme marches publics
          </span>
          <h2 className="mt-5 text-4xl font-extrabold leading-[1.1] tracking-tight text-white drop-shadow-sm">
            L&apos;assistant IA pour vos marches publics
          </h2>
          <p className="mt-4 max-w-md text-white/70">
            Sou9na accompagne les TPME marocaines sur WhatsApp : questions,
            suivi de dossiers, et confirmation humaine a chaque etape sensible.
          </p>
          <div className="mt-10 rounded-2xl border border-white/10 bg-white/[0.06] p-6 backdrop-blur-sm">
            <HeroIllustration />
          </div>
        </div>
      </div>
    </div>
  );
}
