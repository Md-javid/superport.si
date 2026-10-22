/** @type {import('next').NextConfig} */
const rawBackend = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const BACKEND_URL = rawBackend.replace(/\/+$/, "");

module.exports = {
  reactStrictMode: true,
  async rewrites() {
    // The browser only talks to Next.js; /api is proxied to the FastAPI service.
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};
