# プロジェクト永続化の構造改修

## 現状の問題（Explore 調査結果）

Railway のファイルシステムは**デプロイごとにワイプされる**が、VoiceSlide は音声ファイルとスライド画像を Railway のローカルディスクにのみ保存している。そのため：

- **音声ファイル本体** — Supabase Storage にアップロードされていない → 復元時に失われる
- **スライド画像本体** — URL のみ Supabase に保存、実ファイルはローカルディスク
- **audio_job_id** — 保存されていない。スライド URL から正規表現で推測する脆弱な実装

### 今回確認された症状

```
[Restore] ⚠ No old audio found, created silent WAV (60.0s)
[Video] pipeline.timing_map: 0 items
→ 60 秒の無音動画が生成される（音声なし・タイミング崩壊）
```

ユーザーには「動画完成！」と表示されるが、実際は**壊れた動画**が完成している（最悪の UX）。

---

## 修正方針

### Phase 1（即時・今日 deploy）

**目的**: 壊れた動画が完成扱いにならないようにする。ユーザーに明確なフィードバックを提供する。

1. **Fail loudly**: 音声がない状態で動画生成しようとしたら、**500 を返さずに 400** で「音声ファイルが失われています。再アップロードしてください」と明確なメッセージ
2. **再アップロード UI**: フロントの「動画を生成」ボタンが、音声がない場合は「音声を再アップロード」ボタンに変わる
3. **Backend**: `/api/reupload-audio/{job_id}` エンドポイント新設

### Phase 2（短期・1-3 日）

**目的**: Supabase Storage に音声を永続化し、再アップロードが不要になるようにする。

4. **Supabase Storage bucket** `audios` を作成
5. **Upload**: `/api/upload-audio` で音声を Supabase Storage にアップロード。projects テーブルに `audio_storage_path` カラムを追加
6. **Restore**: `/api/restore-project` で Supabase Storage から音声をダウンロード → Railway ローカルに配置 → pipeline に紐付け

### Phase 3（中期・追って実施）

**目的**: スライド画像も Supabase Storage に永続化。

7. スライド画像を Supabase Storage にもアップロード（現在はローカルのみ）
8. 復元時にローカルになければ Storage から fetch

---

## Phase 1 の詳細（今回実装）

### Backend 変更

**`backend/main.py`**:

1. `/api/generate-video/{job_id}`:
   - pipeline の audio が `_placeholder.wav`（無音 WAV）だった場合、400 エラーで返す
   - メッセージ: `音声ファイルが失われています。「音声を再アップロード」ボタンから再度アップロードしてください。`

2. `/api/reupload-audio/{job_id}` 新設:
   - restored pipeline に対して音声を再アップロード
   - 既存の `upload-audio` と同じフローだが、既存の job_id を維持
   - pipeline.audio_path を更新し、既存の placeholder.wav を削除

3. `_create_silent_wav` の呼び出しに `is_placeholder=True` のマーカー（別名にする：`{job_id}_silent_placeholder.wav` のままでも ok。check is filename contains "placeholder"）

### Frontend 変更

**`app/page.tsx`**:

1. restore 完了時に `audio_recovered: bool` を response から受け取り state に保持
2. audio が recovered じゃない場合、「動画を生成」ボタンを「音声を再アップロード」ボタンに変更
3. 再アップロード完了後、「動画を生成」ボタンに戻す

**`backend/main.py` restore-project**:
- response に `audio_recovered: bool` を追加（placeholder なら false）

---

## Phase 2 の詳細（次回実装）

### Supabase スキーマ変更

```sql
ALTER TABLE projects ADD COLUMN audio_storage_path TEXT;
ALTER TABLE projects ADD COLUMN audio_job_id TEXT;
```

### Storage bucket

- `audios`: 認証ユーザーのみアクセス。RLS で user_id + job_id マッチング
- maximum file size: 50MB

### フロー

```
新規：
  音声 upload → Railway local + Supabase Storage (upsert)
  audio_storage_path を projects.settings に保存

復元：
  1. Supabase から project data 取得
  2. audio_storage_path があれば → Storage からダウンロード → Railway local
  3. pipeline.audio_path = ダウンロード先
  4. 音声がなければ Phase 1 と同じく再アップロード促す
```

---

## 検証基準

### Phase 1
- [ ] 新規 → 動画生成完了まで正常
- [ ] 復元 → 「動画を生成」押下 → 400 エラー + UI 変更
- [ ] 再アップロード → 「動画を生成」ボタン復活 → 正常な動画生成

### Phase 2
- [ ] 新規 → Supabase Storage に音声がアップロードされる
- [ ] 復元 → 音声が自動ダウンロード → 動画生成成功
- [ ] デプロイ後の復元でも音声が失われない

---

## スプリント分割

| Sprint | 内容 | 期間 |
|---|---|---|
| 1 | Phase 1: fail-loud + reupload endpoint + UI 切替 | 今日 |
| 2 | Phase 2: Supabase Storage bucket + upload | 次回 |
| 3 | Phase 2: restore で Storage download | 次回 |
| 4 | Phase 3: スライド画像も Storage へ | 追って |
