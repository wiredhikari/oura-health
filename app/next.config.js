/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  experimental: {
    instrumentationHook: false,
  },
  async rewrites() {
    // Talk to the FastAPI service over Railway's private network.
    const apiBase = process.env.API_BASE_URL || "http://api:8000";
    return [
      { source: "/api/backend/:path*", destination: `${apiBase}/:path*` },
    ];
  },
};

module.exports = nextConfig;
