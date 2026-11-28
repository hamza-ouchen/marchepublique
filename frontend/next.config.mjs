/** @type {import('next').NextConfig} */
const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

// Les pages importées de soukna appellent /api/<route> ; l'API FastAPI de
// Sou9na expose surtout les routes SANS préfixe. Les rewrites spécifiques
// passent avant le rewrite générique pour ne pas casser /api/chat.
const SANS_PREFIXE = [
  "auth",
  "onboarding",
  "admin",
  "tenders",
  "entreprises",
  "companies",
  "waitlist",
  "sources",
  "sectors",
  "observability",
  "monitoring",
  "cron",
];

const nextConfig = {
  async rewrites() {
    return {
      // La landing premium (design éditorial) est servie à la racine.
      beforeFiles: [
        { source: "/", destination: "/landing.html" },
        ...SANS_PREFIXE.map((segment) => ({
          source: `/api/${segment}/:path*`,
          destination: `${API_ORIGIN}/${segment}/:path*`,
        })),
      ],
      afterFiles: [
        {
          source: "/api/:path*",
          destination: `${API_ORIGIN}/api/:path*`,
        },
      ],
      fallback: [],
    };
  },
};

export default nextConfig;
