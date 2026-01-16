# VoiceSlide AI Movie 🎬

音声から自動で高品質なプレゼンテーション動画を生成するAI SaaS。

## 🌟 主な機能

- **🎙️ 音声AI処理**: 自動文字起こし、フィラー除去（Strict/Naturalモード）、テキストブラッシュアップ
- **🎨 AIデザイン**: スライド構成生成、自動レイアウト、画像生成
- **🔒 簡易認証**: サイト全体のパスワード保護機能
- **🎬 動画生成**: スライドと音声の自動同期・動画化

---

## 🚀 本番運用マニュアル (Railway)

このアプリケーションは [Railway](https://railway.app/) などのPaaSでの運用を想定しています。

### 1. 新規セットアップ

1. **GitHub連携**: このリポジトリをRailwayなどのプラットフォームにデプロイします。
2. **環境変数の設定**:
   デプロイ先の環境変数設定画面で、`.env.example` の内容を設定します。

   - `SITE_PASSWORD`: サイトに鍵をかけるためのパスワード（**必須**）
   - `OPENAI_API_KEY`: サーバーサイド用（ユーザーがキーを持参しない場合に使用）
   - `GEMINI_API_KEY`: 同上

3. **デプロイ完了**:
   デプロイが完了すると、設定した `SITE_PASSWORD` でログインできるようになります。

### 2. アップデート手順

開発環境（ローカル）で修正を行い、本番環境へ反映する手順です。

1. **ローカルで開発**: コードを修正・テストします。
2. **Git Push**:
   ```bash
   git add .
   git commit -m "機能追加: 〇〇機能"
   git push origin main
   ```
3. **自動デプロイ**:
   GitHubの `main` ブランチにプッシュされると、Railwayが自動的に検知して再ビルド・デプロイを行います（数分かかります）。

### 3. 環境変数リファレンス

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `SITE_PASSWORD` | ✅ | ログイン画面のパスワード。未設定だと全公開状態になります。 |
| `OPENAI_API_KEY` | ✅ | AI機能の呼び出し用。 |
| `GEMINI_API_KEY` | ✅ | AI機能の呼び出し用。 |
| `Frontend URL` | - | Next.jsが `$PORT` で起動します。 |
| `NEXT_PUBLIC_API_URL` | - | 基本的に**設定不要**（空欄）です。内部プロキシが自動処理します。 |

---

## 💻 ローカル開発環境 (Mac)

### セットアップ

```bash
# 依存関係インストール
cd voiceslide-ai
npm install
cd backend
pip install -r requirements.txt
playwright install chromium

# 環境変数（開発用）
cp .env.example .env.local
# .env.local を開き、APIキーなどを入力してください
```

### 起動

```bash
# ワンライナー起動（バックエンド+フロントエンド）
chmod +x start-local.sh
./start-local.sh
```

- フロントエンド: http://localhost:3000
- バックエンド: http://localhost:8000

---

## ⚠️ トラブルシューティング

**Q. 画像がスライドに反映されない**
- ユーザー画像は `div` タグと `z-index` 指定で配置されます。ログに `[Design Architect] WARNING` が出ていないか確認してください。

**Q. デプロイ後にエラーになる**
- Railwayの「Logs」を確認してください。APIキーやパスワードの設定漏れがないかチェックしてください。

**Q. ログインできない**
- `SITE_PASSWORD` が正しく設定されているか確認してください。設定変更後は再デプロイが必要です。
