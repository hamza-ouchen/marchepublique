"use client";

// Écran de chargement de marque : logo + anneau de progression + message
// contextuel. Utilisé par l'invitation, le tableau de bord entreprise et la
// console admin. Les étapes optionnelles rendent l'attente explicite et
// rassurante (préparation des offres, du profil entreprise, etc.).

export default function BrandLoader({
  label,
  steps = [],
  showProgress = false,
}: {
  label: string;
  steps?: string[];
  showProgress?: boolean;
}) {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center bg-paper gap-5 px-4"
      role="status"
      aria-live="polite"
    >
      <div className="relative w-16 h-16 flex items-center justify-center">
        <span className="absolute inset-0 rounded-full border-2 border-greenbrand/20 border-t-greenbrand animate-spin" />
        <svg className="w-8 h-8 text-greenbrand" viewBox="0 0 40 40" fill="none" aria-hidden="true">
          <path d="M20 2 38 20 20 38 2 20Z" fill="currentColor" />
          <path d="M20 10 30 20 20 30 10 20Z" fill="#f5f0e6" />
          <path d="M20 15 25 20 20 25 15 20Z" fill="#c2603a" />
        </svg>
      </div>

      <div className="text-center">
        <span className="font-display text-xl font-bold text-ink tracking-tight">Sou9na</span>
        <p className="text-xs text-muted mt-1">{label}</p>
      </div>

      {(showProgress || steps.length > 0) && (
        <div className="w-full max-w-sm">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-greenbrand/15">
            <div className="h-full w-1/3 rounded-full bg-greenbrand animate-pulse" />
          </div>
          {steps.length > 0 && (
            <ul className="mt-4 space-y-1.5">
              {steps.map((step, index) => (
                <li key={step} className="flex items-center gap-2 text-[11px] text-muted">
                  <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-greenbrand/10 text-[9px] font-bold text-greenbrand">
                    {index + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
