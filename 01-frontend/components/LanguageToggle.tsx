"use client";

import { useLanguage } from "@/lib/i18n";
import clsx from "clsx";

export function LanguageToggle({ className }: { className?: string }) {
  const { lang, toggleLang } = useLanguage();

  return (
    <button
      type="button"
      onClick={toggleLang}
      aria-label="Changer de langue"
      title={lang === "fr" ? "Switch to Arabic" : "التبديل إلى الفرنسية"}
      className={clsx(
        "inline-flex h-9 min-w-9 shrink-0 items-center justify-center rounded-full border border-sand-200 bg-surface px-2.5 text-xs font-semibold text-sand-900/70 shadow-sm transition-colors hover:bg-sand-50 hover:text-sand-900",
        className
      )}
    >
      {lang === "fr" ? "عربي" : "FR"}
    </button>
  );
}
