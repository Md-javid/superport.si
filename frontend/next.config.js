/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

module.exports = {
  reactStrictMode: true,
  async rewrites() {
    // The browser only talks to Next.js; /api is proxied to the FastAPI service.
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};
