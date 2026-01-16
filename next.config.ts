import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 出力ファイルとAPIへのアクセスをプロキシ（Railway等の1コンテナ構成用）
  async rewrites() {
    return [
      {
        source: '/outputs/:path*',
        destination: 'http://localhost:8001/outputs/:path*',
      },
      {
        source: '/api/:path*',
        destination: 'http://localhost:8001/api/:path*',
      },
    ];
  },
};

export default nextConfig;
