import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async redirects() {
    return [
      { source: "/approvals", destination: "/opportunities", permanent: true },
      { source: "/quality", destination: "/opportunities", permanent: true },
    ];
  },
};

export default nextConfig;
