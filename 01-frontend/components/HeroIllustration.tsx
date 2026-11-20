export function HeroIllustration() {
  return (
    <svg
      viewBox="0 0 480 420"
      className="h-auto w-full max-w-md"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* Arche de fond */}
      <path
        d="M60 380V200C60 117 127 50 210 50H270C353 50 420 117 420 200V380"
        className="stroke-brand-200"
        strokeWidth="3"
        fill="none"
      />

      {/* Carte "document / appel d'offres" */}
      <g transform="translate(70 150)">
        <rect width="190" height="140" rx="14" className="fill-white" stroke="currentColor" strokeOpacity="0.08" />
        <rect x="20" y="24" width="110" height="10" rx="5" className="fill-sand-200" />
        <rect x="20" y="48" width="150" height="8" rx="4" className="fill-sand-100" />
        <rect x="20" y="64" width="150" height="8" rx="4" className="fill-sand-100" />
        <rect x="20" y="80" width="90" height="8" rx="4" className="fill-sand-100" />
        <rect x="20" y="104" width="70" height="22" rx="11" className="fill-brand-50" />
        <text x="35" y="119" className="fill-brand-700" fontSize="11" fontWeight="500">
          Appel d&apos;offre
        </text>
      </g>

      {/* Bulle de chat WhatsApp */}
      <g transform="translate(230 70)">
        <rect width="200" height="110" rx="20" className="fill-brand-600" />
        <path d="M24 110 L24 134 L52 110 Z" className="fill-brand-600" />
        <rect x="24" y="24" width="130" height="10" rx="5" fill="white" fillOpacity="0.9" />
        <rect x="24" y="46" width="152" height="8" rx="4" fill="white" fillOpacity="0.55" />
        <rect x="24" y="62" width="110" height="8" rx="4" fill="white" fillOpacity="0.55" />
        <rect x="24" y="84" width="90" height="20" rx="10" fill="white" fillOpacity="0.95" />
      </g>

      {/* Check / validation humaine (HITL) */}
      <g transform="translate(330 260)">
        <circle cx="30" cy="30" r="30" className="fill-brand-500" />
        <path
          d="M18 31L26 39L43 21"
          stroke="white"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </g>

      {/* Petits points decoratifs */}
      <circle cx="90" cy="110" r="4" className="fill-brand-300" />
      <circle cx="400" cy="130" r="5" className="fill-brand-200" />
      <circle cx="140" cy="340" r="4" className="fill-brand-300" />
    </svg>
  );
}
