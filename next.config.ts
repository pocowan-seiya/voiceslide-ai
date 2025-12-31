import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 出力ファイルへのアクセスをプロキシ
  async rewrites() {
    return [
      {
        source: '/outputs/:path*',
        destination: 'http://localhost:8001/outputs/:path*',
      },
    ];
  },
};

export default nextConfig;
