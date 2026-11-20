export function LogoMark({ size = 36 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <rect width="36" height="36" rx="10" className="fill-brand-600" />
      {/* Arche stylisee (motif architecture marocaine) representant le "souk" */}
      <path
        d="M11 25.5V17.5C11 13.634 14.134 10.5 18 10.5C21.866 10.5 25 13.634 25 17.5V25.5"
        stroke="white"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M11 25.5H25"
        stroke="white"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <circle cx="18" cy="18.5" r="1.6" className="fill-brand-600" stroke="white" strokeWidth="1.4" />
    </svg>
  );
}

export function Logo({
  className = "",
  size = 36,
  textClassName = "text-lg",
}: {
  className?: string;
  size?: number;
  textClassName?: string;
}) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <LogoMark size={size} />
      <span className={`font-semibold tracking-tight text-sand-900 ${textClassName}`}>
        Sou9na
      </span>
    </div>
  );
}
