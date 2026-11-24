/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return {
      // La landing premium (design éditorial) est servie à la racine.
      beforeFiles: [{ source: "/", destination: "/landing.html" }],
      afterFiles: [
        {
          source: "/api/:path*",
          destination: `${(process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "")}/api/:path*`,
        },
      ],
      fallback: [],
    };
  },
};

export default nextConfig;
