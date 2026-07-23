/** @type {import('next').NextConfig} */
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const nextConfig = {
  async rewrites() {
    // Proxy API calls to the FastAPI backend so the browser hits same-origin.
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

module.exports = nextConfig;
