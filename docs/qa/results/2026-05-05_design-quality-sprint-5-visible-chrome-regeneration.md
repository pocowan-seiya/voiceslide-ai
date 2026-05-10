# 2026-05-05 Design Quality Sprint 5 visible Chrome regeneration QA

実施日時: 2026-05-05 10:18〜10:23 JST  
対象: VoiSlide Movie fixed fixture regeneration after Sprint 5 text-safety fallback telemetry  
frontend: `http://127.0.0.1:3010/`  
backend: `http://127.0.0.1:8001`  
CDP: `http://127.0.0.1:9223`  
fixture: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`

## 結論

Sprint 5の狙いだった「TextSafety由来のslide単位fallback reasonを実データで見えるようにする」は確認できた。

Sprint 4再生成では、`fallback_used=true` が残っていてもtelemetryは `Strategy generation failed` しか見えなかった。  
Sprint 5再生成では、以下がtelemetryに出た。

- `fallback:Strategy generation failed`
- `fallback:TextSafety fallback: title missing`

これで、strategy fallback と TextSafety fallback が分離して見えるようになった。

一方で、quality gateはSprint 4と同じく4枚中2枚pass。  
`flash_standard` は2/2 pass、`pro` は2/2 fail。

## API key handling

共有Chrome profileのlocalStorageからAPIキーを一時メモリに読み、backend headerへ渡して実生成した。  
値は出力・保存していない。保存したのはpresenceのみ。

```json
{
  "openai": true,
  "gemini": true,
  "geminiModel": true,
  "openrouter": true,
  "openrouterModel": true,
  "openrouterDesignModel": true
}
```

## Generated runs

### flash_standard

- job_id: `c80e32b9-3aa0-4a94-9e15-96c1a1c9e07d`
- telemetry:
  - `entry_count=8`
  - `total_calls=8`
  - `fallback_count=3`
- stage counts:
  - `strategy=1`
  - `fallback=3`
  - `slide_html=2`
  - `self_review=2`
- fallback reasons:
  - `Strategy generation failed`: 1
  - `TextSafety fallback: title missing`: 2

Design quality:

| slide | min_font_size_px | small_text_count | fallback_used | quality_gate |
|---:|---:|---:|---|---|
| 1 | 22.0 | 0 | true | pass |
| 2 | 22.0 | 0 | true | pass |

### pro

- job_id: `8d894ee0-6216-4055-9bc4-8f91255ff0ba`
- telemetry:
  - `entry_count=7`
  - `total_calls=7`
  - `fallback_count=2`
- stage counts:
  - `strategy=1`
  - `fallback=2`
  - `slide_html=2`
  - `self_review=2`
- fallback reasons:
  - `Strategy generation failed`: 1
  - `TextSafety fallback: title missing`: 1

Design quality:

| slide | min_font_size_px | title_font_size_px | small_text_count | fallback_used | quality_gate |
|---:|---:|---:|---:|---|---|
| 1 | 13.6 | 48.0 | 2 | false | fail |
| 2 | 16.0 | 88.0 | 1 | true | fail |

## Hash comparison

Sprint 5 artifacts:

| file | sha256 | size |
|---|---|---:|
| `flash_standard_slide_001.png` | `abb51af2c42058ea51f5035bc260dfaa3eb00a18cea714ef2787592f3c6bb8c7` | 717098 |
| `flash_standard_slide_002.png` | `cbed7a9ff8e9b2c4ee570aa3cd390f54175102ca8eace5abc6194fa14cf97057` | 655400 |
| `pro_slide_001.png` | `71a32377cc9f8595f59834ecc2d094a76b53ea03f5a99084bab8f9763c0ab36e` | 1002101 |
| `pro_slide_002.png` | `0e81578eee2ff61bb1ce3d076b14daabd899665d894fccb20d1963943e2075e2` | 771610 |

`pro` と `flash_standard` は別hash。  
mode collapseは再発していない。

## Sprint 4 → Sprint 5 comparison

| mode | slide | Sprint 4 gate | Sprint 4 fallback_count | Sprint 4 fallback reasons | Sprint 5 gate | Sprint 5 fallback_count | Sprint 5 fallback reasons |
|---|---:|---|---:|---|---|---:|---|
| flash_standard | 1 | pass | 1 | Strategy only | pass | 3 | Strategy + TextSafety title missing |
| flash_standard | 2 | pass | 1 | Strategy only | pass | 3 | Strategy + TextSafety title missing |
| pro | 1 | fail | 1 | Strategy only | fail | 2 | Strategy + TextSafety title missing at job level |
| pro | 2 | fail | 1 | Strategy only | fail | 2 | Strategy + TextSafety title missing |

注意: `fallback_count` はjob summaryなので、mode内のfallback event合計。Sprint 5ではTextSafety eventが増えた分、`total_calls` / `entry_count` も増えた。

## Key finding

`TextSafety fallback: title missing` が実データで出た。

これは、生成HTMLのvisible textに期待titleが見つからないと判定され、fallback HTMLへ置き換わったことを意味する。  
ただし、vision上は明らかな壊れたfallbackには見えない。fallback template自体が一定品質を持っているため。

次に見るべきは、なぜtitle missingになるか。

候補:

1. AI生成側がtitleを書き換えている
2. self-reviewでtitleが変わっている
3. `_title_present()` の正規化/部分一致が日本語タイトルに厳しすぎる
4. gradient text / DOM構造の影響でvisible text取得が期待通りでない

## Vision QA summary

`comparison_contact_sheet.jpg` をvision確認した。

- 全体はdark cinematicで統一されている
- `pro` は `flash_standard` より明確にpremium
- `pro slide 1` は構図・背景・装飾が良い
- `pro slide 2` も構図は良い
- ただし小さいfooter / caption / bullet / card textが残る
- metric上の `pro` failは見た目の悪さというより、小さい補助/装飾テキストとtitle size不足を拾っている

## Artifacts

Folder:

`docs/qa/results/2026-05-05_design-quality-sprint-5-visible-chrome-regeneration/`

Files:

- `sanitized_api_result.json`
- `artifact_hashes.json`
- `summary.json`
- `comparison_contact_sheet.jpg`
- `flash_standard_slide_001.png`
- `flash_standard_slide_002.png`
- `pro_slide_001.png`
- `pro_slide_002.png`

## Next actions

1. `TextSafety fallback: title missing` の原因をTDDで切る
   - self-review前後のtitle保持
   - `_title_present()` の日本語判定
   - generated HTML visible textのsnapshot
2. `pro` のdecorative/footer textをquality gate上どう扱うか整理する
3. `total_calls` がlocal fallback eventも含む問題を、将来UI用に `total_events` / `ai_call_count` へ分離する

## commit / push

未実施。
