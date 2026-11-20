"use client";

import { Sun, Moon } from "lucide-react";
import { useTheme } from "@/lib/theme-context";
import clsx from "clsx";

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label="Changer de theme"
      title={theme === "dark" ? "Passer au mode clair" : "Passer au mode sombre"}
      className={clsx(
        "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-sand-200 bg-surface text-sand-900/70 shadow-sm transition-colors hover:bg-sand-50 hover:text-sand-900",
        className
      )}
    >
      {theme === "dark" ? (
        <Sun className="h-[18px] w-[18px]" />
      ) : (
        <Moon className="h-[18px] w-[18px]" />
      )}
    </button>
  );
}
