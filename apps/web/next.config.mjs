/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/discovery/:path*",
        destination: "http://localhost:8003/:path*",
      },
      {
        source: "/api/permits/:path*",
        destination: "http://localhost:8002/:path*",
      },
      {
        source: "/api/llm/:path*",
        destination: "http://localhost:8006/:path*",
      },
    ];
  },
};

export default nextConfig;
