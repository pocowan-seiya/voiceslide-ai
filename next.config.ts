import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 2サービス構成: Frontend (Next.js) + Backend (FastAPI) を別々にデプロイ
  // NEXT_PUBLIC_API_URL 環境変数でバックエンドURLを指定
  // リライトは不要（直接バックエンドにアクセス）
};

export default nextConfig;

