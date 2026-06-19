/** @type {import('next').NextConfig} */
const DISCOVERY_URL = process.env.DISCOVERY_API_URL ?? "http://localhost:8003";
const PERMITS_URL = process.env.PERMIT_SERVICE_URL ?? "http://localhost:8002";
const LLM_URL = process.env.LLM_GATEWAY_URL ?? "http://localhost:8006";
const SPE_URL = process.env.SPE_PROVISIONER_URL ?? "http://localhost:8004";

const nextConfig = {
  async rewrites() {
    return [
      { source: "/api/discovery/:path*", destination: `${DISCOVERY_URL}/:path*` },
      { source: "/api/permits/:path*",   destination: `${PERMITS_URL}/:path*` },
      { source: "/api/llm/:path*",       destination: `${LLM_URL}/:path*` },
      { source: "/api/spe/:path*",       destination: `${SPE_URL}/:path*` },
      { source: "/api/audit/:path*",     destination: `${PERMITS_URL}/audit/:path*` },
    ];
  },
};

export default nextConfig;
