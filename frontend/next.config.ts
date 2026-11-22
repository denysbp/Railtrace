import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // The browser calls /api/... and Next.js forwards it to the FastAPI /v1/...
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/v1/:path*` }];
  },
};

export default nextConfig;
