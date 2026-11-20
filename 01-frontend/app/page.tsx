"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth, roleHome } from "@/lib/auth-context";
import { Logo } from "@/components/Logo";
import { HeroIllustration } from "@/components/HeroIllustration";
import { ThemeToggle } from "@/components/ThemeToggle";
import { MessageCircle, ShieldCheck, Languages, ArrowRight } from "lucide-react";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading || !user) return;
    router.replace(roleHome(user.role));
  }, [loading, user, router]);

  if (loading || user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-sand-50">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-sand-50">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Logo />
        <nav className="flex items-center gap-3">
          <ThemeToggle />
          <Link href="/login" className="btn-secondary !px-4 !py-2 text-sm">
            Se connecter
          </Link>
          <Link href="/signup" className="btn-primary !px-4 !py-2 text-sm">
            Creer un compte
          </Link>
        </nav>
      </header>

      <main className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-12 px-6 py-12 lg:grid-cols-2 lg:py-20">
        <div>
          <span className="badge badge-dot border border-brand-100 bg-brand-50 text-brand-700">
            Plateforme IA marches publics
          </span>
          <h1 className="mt-6 text-5xl font-extrabold leading-[1.05] tracking-tight text-sand-900 sm:text-6xl">
            Repondez aux appels d&apos;offres{" "}
            <span className="text-brand-600">sans rater une ligne.</span>
          </h1>
          <p className="mt-6 max-w-lg text-base leading-relaxed text-sand-900/60">
            Sou9na accompagne votre TPME sur WhatsApp — en francais, arabe ou
            darija. Reponses sourcees, et toujours une confirmation humaine
            avant toute action sensible.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link href="/signup" className="btn-primary">
              Creer mon compte TPME
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link href="/login" className="btn-secondary">
              J&apos;ai deja un compte
            </Link>
          </div>
          <p className="mt-3 text-xs text-sand-900/40">
            Gratuit pour commencer · Aucune carte bancaire requise
          </p>

          <div className="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-3">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                <MessageCircle className="h-[18px] w-[18px]" />
              </div>
              <div>
                <p className="text-sm font-medium text-sand-900">Sur WhatsApp</p>
                <p className="text-xs text-sand-900/50">Pas d&apos;app a installer</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                <Languages className="h-[18px] w-[18px]" />
              </div>
              <div>
                <p className="text-sm font-medium text-sand-900">FR / AR / Darija</p>
                <p className="text-xs text-sand-900/50">Dans votre langue</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                <ShieldCheck className="h-[18px] w-[18px]" />
              </div>
              <div>
                <p className="text-sm font-medium text-sand-900">Confirmation humaine</p>
                <p className="text-xs text-sand-900/50">Jamais d&apos;action seule</p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-center lg:justify-end">
          <HeroIllustration />
        </div>
      </main>
    </div>
  );
}
