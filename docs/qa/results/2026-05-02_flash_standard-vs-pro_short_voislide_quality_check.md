# デザイン品質比較 QA — flash_standard vs pro / short_voislide_quality_check

## 基本情報

| 項目 | 値 |
|------|---|
| 実施日 | 2026-05-02 |
| 評価者 | Hermes Agent |
| 音声サンプル | `docs/qa/fixtures/short_voislide_quality_check_32s.mp3` |
| 比較目的 | `flash_standard` と `pro` を同一入力で比較するための初回QA。今回は実生成前の環境確認・固定サンプル作成・ブロッカー特定まで。 |

---

## 今回実施したこと

1. 固定音声サンプルを追加
   - `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`
   - `docs/qa/fixtures/short_voislide_quality_check_32s.txt`
   - 長さ: 32.429 秒
   - サイズ: 227,767 bytes
   - 内容: 文字忠実度、読みやすさ、余白、音声同期、保存・復元を確認する短い合成音声

2. `docs/qa/fixtures/README.md` を更新
   - 現在のサンプル一覧に上記サンプルを追加

3. 自動チェック
   - `npm test -- --watch=false`
     - 8 suites passed
     - 98 tests passed
     - 既存想定の console.error ログあり: `Header onBeforeNavigate failed` をテスト内で発生させるケース
   - `cd backend && ./venv/bin/python -m pytest tests/test_design_mode.py -q`
     - 7 passed
     - httplib2/pyparsing由来のDeprecationWarningあり
   - `npm run build`
     - Build passed
     - Warning: Next.js workspace root推定
     - Warning: `middleware` convention deprecated, `proxy` 推奨

4. ローカルBackend確認
   - `PORT=8001 ./venv/bin/python main.py`
   - `GET http://127.0.0.1:8001/` → 200
   - `POST /api/upload-audio` に固定音声をアップロード → 200
   - 返却job_id: `e81b2a97-871c-4fb1-bec5-22341e3b81f7`
   - `audio_storage_status`: `skipped`
   - 理由: `missing_user_or_project_id`（ローカルAPI直接実行のため想定内）

5. 文字起こし開始確認
   - `POST /api/transcribe/{job_id}?cleanup_audio=false` → 200
   - `GET /api/transcribe-status/{job_id}` → error
   - エラー: `OpenAI API key is required. Please set it in settings.`

---

## モード A: flash_standard

| 項目 | 値 |
|------|---|
| モード名 | flash_standard |
| モデル ID | 未実行 |
| 生成時間 | 未計測 |
| 推定 API コスト | 未計測 |
| エラー/フォールバック | 生成前ブロック。OpenAI/Gemini/OpenRouter APIキーがローカルHermes実行環境に未設定。 |

### ルーブリックスコア

| # | 項目 | スコア (1-5) | コメント |
|---|------|:---:|----------|
| 1 | Copy Fidelity | N/A | 文字起こし未完了のため未採点 |
| 2 | Readability | N/A | スライド生成未完了のため未採点 |
| 3 | Whitespace | N/A | スライド生成未完了のため未採点 |
| 4 | Visual Hierarchy | N/A | スライド生成未完了のため未採点 |
| 5 | Continuity | N/A | スライド生成未完了のため未採点 |
| 6 | Audio Fit | N/A | 動画生成未完了のため未採点 |
| 7 | Editability | N/A | スライド生成未完了のため未採点 |
| 8 | Restore Safety | N/A | DB/Storage連携なしのAPI直接実行のため未採点 |
| 9 | Performance | N/A | 生成未完了のため未採点 |
| 10 | Cost Awareness | N/A | API実行なし |
| | **合計** | N/A | |

---

## モード B: pro

| 項目 | 値 |
|------|---|
| モード名 | pro |
| モデル ID | 未実行 |
| 生成時間 | 未計測 |
| 推定 API コスト | 未計測 |
| エラー/フォールバック | 生成前ブロック。OpenAI/Gemini/OpenRouter APIキーがローカルHermes実行環境に未設定。 |

### ルーブリックスコア

| # | 項目 | スコア (1-5) | コメント |
|---|------|:---:|----------|
| 1 | Copy Fidelity | N/A | 文字起こし未完了のため未採点 |
| 2 | Readability | N/A | スライド生成未完了のため未採点 |
| 3 | Whitespace | N/A | スライド生成未完了のため未採点 |
| 4 | Visual Hierarchy | N/A | スライド生成未完了のため未採点 |
| 5 | Continuity | N/A | スライド生成未完了のため未採点 |
| 6 | Audio Fit | N/A | 動画生成未完了のため未採点 |
| 7 | Editability | N/A | スライド生成未完了のため未採点 |
| 8 | Restore Safety | N/A | DB/Storage連携なしのAPI直接実行のため未採点 |
| 9 | Performance | N/A | 生成未完了のため未採点 |
| 10 | Cost Awareness | N/A | API実行なし |
| | **合計** | N/A | |

---

## 比較サマリ

| 項目 | flash_standard | pro |
|------|:---:|:---:|
| 合計スコア | N/A | N/A |
| 生成時間 | N/A | N/A |
| コスト | N/A | N/A |
| 失敗 | APIキー未設定で生成前停止 | APIキー未設定で生成前停止 |

## 結論

- 固定音声サンプル、比較テンプレ、基本チェックは準備完了。
- 実際の `flash_standard` / `pro` 比較QAは、Hermesが使う実行環境にAI APIキーがないため未実行。
- APIキー不足はアプリの回帰ではなく、QA環境ブロッカー。
- 次は、共有Chromeプロファイルまたは安全なローカル環境変数でAPIキーを設定し、同じ音声サンプルで本比較を実行する。

## 次のアクション

1. visible Chrome/CDP共有QAで、誠哉さんがキーを画面入力する。
2. Hermesはキー値を見ずに、設定済み状態だけ確認する。
3. `short_voislide_quality_check_32s.mp3` を使って、`flash_standard` と `pro` を生成する。
4. 生成物をこのファイルに追記し、ルーブリック採点する。
5. 結果をProduct Ops Boardへ反映する。


---

## 2026-05-02 17:27 JST 追記: visible Chrome/CDP 実生成比較

### 実行条件

- 実行方法: visible Chrome/CDP共有QA
- Frontend: `http://127.0.0.1:3000/`
- Backend: `http://127.0.0.1:8001/`
- Project URL: `http://127.0.0.1:3000/?project=220945e0-0a55-4c4d-9281-27bffebb87e9`
- job_id: `7469894c-7c49-49a5-807d-885cfb35681a`
- 音声fixture: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`
- 生成スライド数: 2枚
- APIキー: 共有Chromeの画面設定を使用。値は取得・保存していない。

### 保存した生成物

- `docs/qa/results/2026-05-02_flash_standard-vs-pro_short_voislide_quality_check/flash_standard_slide_001.png`
- `docs/qa/results/2026-05-02_flash_standard-vs-pro_short_voislide_quality_check/flash_standard_slide_002.png`
- `docs/qa/results/2026-05-02_flash_standard-vs-pro_short_voislide_quality_check/pro_slide_001.png`
- `docs/qa/results/2026-05-02_flash_standard-vs-pro_short_voislide_quality_check/pro_slide_002.png`
- `docs/qa/results/2026-05-02_flash_standard-vs-pro_short_voislide_quality_check/comparison_contact_sheet.jpg`
- `docs/qa/results/2026-05-02_flash_standard-vs-pro_short_voislide_quality_check/pro_video.mp4`

### 生成物サイズ / 短縮SHA256

| ファイル | サイズ | SHA256先頭16桁 |
|---|---:|---|
| `comparison_contact_sheet.jpg` | 120,844 | `c2fe60c974401eca` |
| `flash_standard_slide_001.png` | 717,098 | `abb51af2c42058ea` |
| `flash_standard_slide_002.png` | 673,874 | `b643476f26cf8019` |
| `pro_slide_001.png` | 1,098,259 | `9f8f5a3c89b483b3` |
| `pro_slide_002.png` | 673,874 | `b643476f26cf8019` |
| `pro_video.mp4` | 1,013,352 | `c8fa93ddea46ec97` |

### 動画生成確認

- `pro` 側の最終動画生成まで完了。
- `ffprobe` 結果:
  - duration: `32.433333` 秒
  - size: `1,013,352` bytes
- UI上のタイムライン:
  - スライド1: 0:00 → 0:25（25.5秒）
  - スライド2: 0:25 → 0:32（6.9秒）

### 比較結果

結論: **今回の固定fixtureでは `pro` が優位。**

主な差は1枚目の表紙スライド。
`pro` はタイトルを2行に分け、余白と視覚階層が明確だった。
`flash_standard` は中央に情報が集まり、補足テキストが小さく、表紙として説明過多に見えた。

2枚目は `flash_standard` と `pro` が同一画像だった。
そのため、今回の差分は主に表紙生成テンプレート/プロンプト側で出ている。

### ルーブリック暫定スコア

| # | 項目 | flash_standard | pro | コメント |
|---|---:|:---:|:---:|---|
| 1 | Copy Fidelity | 4 | 4 | 音声趣旨は反映。完全逐語ではなく要約スライド化。 |
| 2 | Readability | 3 | 4 | pro表紙はタイトルが大きく読みやすい。flashは小さい補足が多い。 |
| 3 | Whitespace | 3 | 4 | pro表紙は余白が意図的。flashは中央に情報が密集。 |
| 4 | Visual Hierarchy | 3 | 4 | proはバッジ、タイトル、サブタイトル、フッターの階層が明確。 |
| 5 | Continuity | 3 | 4 | proは表紙と内容スライドの統一感が高い。 |
| 6 | Audio Fit | 4 | 4 | 32秒音声に2枚構成で自然。スライド1が25.5秒、スライド2が6.9秒。 |
| 7 | Editability | 4 | 4 | 生成後UIでスライド差し替え、複製、削除、タイムライン編集が可能。 |
| 8 | Restore Safety | 4 | 4 | ローカルプロジェクト保存状態で再表示できた。長期復元は別QA対象。 |
| 9 | Performance | 4 | 4 | 実生成は完了。スライド生成時間は今回厳密計測なし。動画生成は約10秒で完了。 |
| 10 | Cost Awareness | 3 | 3 | APIコストはUI/ログで未計測。比較QAには今後の計測項目として残す。 |
| | **合計** | **35/50** | **39/50** | `pro` 優位。 |

### 観察メモ

- `pro_slide_002.png` と `flash_standard_slide_002.png` はSHA256が一致した。
  - 2枚目は両モードで同じ画像。
  - 今回の差分検出には、1枚目だけではなく複数fixtureでの再試行が必要。
- `pro_slide_001.png` は `flash_standard_slide_001.png` よりファイルサイズが大きく、装飾密度も高い。
- `pro` の表紙は表紙としての完成度が高いが、2枚目のカード内テキストはまだ小さい。
- 次の改善対象は「内容スライドのカード文字サイズ」と「コスト/生成時間の自動記録」。

### 次のアクション

1. 同じfixtureで `flash_standard` も動画生成まで完了させ、動画同士で音声同期を比較する。
2. 別fixtureを追加し、2枚目以降でも `pro` 差分が出るか確認する。
3. QAログに生成開始/終了時刻、使用モデル、推定コストを自動追記する仕組みを検討する。
4. 将来の `image-background` モードを同じルーブリックに追加する。
