---
description: VoiSlide AIのデプロイ時に必ず確認すべきCORS設定
---

# VoiSlide デプロイ時CORSチェックリスト

## デプロイ前の確認

1. **現在のRailway URL確認**
   - フロントエンド: `https://voiceslide-ai-{環境}.up.railway.app`
   - バックエンド: `https://backend-api-{環境}-{ID}.up.railway.app`

2. **CORS設定確認**
   ```bash
   grep -A 15 "cors_origins = \[" backend/main.py
   ```

3. **新しいURLが含まれているか確認**
   - 含まれていなければ追加してからデプロイ

## 現在の許可済みURL（2026-01-28時点）

```python
cors_origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "https://voiceslide-ai-development.up.railway.app",
    "https://voiceslide-ai-production.up.railway.app",
    "https://backend-api-development-58ec.up.railway.app",
    "https://backend-api-production-391c.up.railway.app",
    "https://voiceslide.movie",
]
```

## 新しいURLを追加する場合

1. `backend/main.py`のcors_originsリストに追加
2. コミット & プッシュ
3. 両ブランチ（main/develop）に反映

## トラブルシューティング

エラー例:
```
Access to fetch at 'https://backend-api-xxx.up.railway.app/...' 
from origin 'https://voiceslide-ai-xxx.up.railway.app' 
has been blocked by CORS policy
```

→ 上記URLがcors_originsに含まれているか確認
