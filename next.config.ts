import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // APIリクエストをバックエンド（ポート8001）にプロキシ
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8001/api/:path*',
      },
      {
        source: '/outputs/:path*',
        destination: 'http://localhost:8001/outputs/:path*',
      },
    ];
  },
};

export default nextConfig;
