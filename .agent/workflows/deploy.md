---
description: VoiSlide AIのデプロイ手順（develop → main）
---

# VoiSlide AI デプロイワークフロー

## 基本ルール
- **本番 (`main`) を直接変更しない**
- develop でテスト → 確認後に main へマージ

## 手順

### 1. 変更をdevelopにデプロイ
```bash
cd /Users/seiyaeto/Antigravity/voiceslide-ai
git checkout develop
git add -A
git commit -m "変更内容"
git push origin develop
```

### 2. developで動作確認
- Railway develop環境でテスト
- 問題なければ次へ

### 3. mainにマージ（本番デプロイ）
```bash
git checkout main
git merge develop
git push origin main
```

## 注意
- mainへのpushは本番サーバーが再起動し、進行中のジョブが消失する
- 大きな変更は利用者が少ない時間帯に実施推奨
