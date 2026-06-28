# 2026-05-04 Design Quality Sprint 4 visible Chrome regeneration QA

実施日時: 2026-05-04 22:32〜22:38 JST  
対象: VoiSlide Movie fixed fixture regeneration after Sprint 4 fallback mode / telemetry  
frontend: `http://127.0.0.1:3010/`  
backend: `http://127.0.0.1:8001`  
CDP: `http://127.0.0.1:9223`  
fixture: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`

## 結論

Sprint 4の狙いだった「`pro` slide 1 と `flash_standard` slide 1 の同一hash解消」は確認できた。

Sprint 3では `flash_standard_slide_001.png` と `pro_slide_001.png` が同一hashだった。  
Sprint 4再生成では4枚すべてhashが分かれた。

一方で、quality gateは後退した。  
Sprint 3は4枚中3枚passだったが、Sprint 4再生成では4枚中2枚pass。  
`pro` は2枚とも `quality_gate=fail` になった。

これはSprint 4のfallback variant修正そのものより、今回の実生成結果で小さい装飾/補助テキストが増えた影響が大きい。Vision上は `pro` の見た目は明確に良くなっているが、metric上は小さい文字を拾ってfailになっている。

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

- job_id: `788a532c-4341-4f1c-8531-5424c94960cd`
- transcript_length: 189
- outline_slide_count: 2
- telemetry:
  - `entry_count=6`
  - `total_calls=6`
  - `fallback_count=1`
  - `total_duration_ms=78409`
- stage counts:
  - `strategy=1`
  - `fallback=1`
  - `slide_html=2`
  - `self_review=2`
- fallback reason:
  - `Strategy generation failed`: 1

Design quality:

| slide | min_font_size_px | small_text_count | fallback_used | quality_gate |
|---:|---:|---:|---|---|
| 1 | 22.0 | 0 | true | pass |
| 2 | 22.0 | 0 | true | pass |

### pro

- job_id: `988d5a16-e39f-4164-b96e-caab4f213caf`
- transcript_length: 189
- outline_slide_count: 2
- telemetry:
  - `entry_count=6`
  - `total_calls=6`
  - `fallback_count=1`
- stage counts:
  - `strategy=1`
  - `fallback=1`
  - `slide_html=2`
  - `self_review=2`
- fallback reason:
  - `Strategy generation failed`: 1

Design quality:

| slide | min_font_size_px | small_text_count | fallback_used | quality_gate |
|---:|---:|---:|---|---|
| 1 | 14.0 | 4 | false | fail |
| 2 | 16.0 | 1 | true | fail |

## Hash comparison

Sprint 4 artifacts:

| file | sha256 | size |
|---|---|---:|
| `flash_standard_slide_001.png` | `abb51af2c42058ea51f5035bc260dfaa3eb00a18cea714ef2787592f3c6bb8c7` | 717098 |
| `flash_standard_slide_002.png` | `3179e11eeee8ef954e3b86838b223c012ce40917e18f7ebd8d0c2a1164225439` | 655227 |
| `pro_slide_001.png` | `56f632b57ae227bbf0855feea820508e8e2cca99859066845d9b1ae5eeb45ef6` | 961898 |
| `pro_slide_002.png` | `7ecd3111dad9a38412d73e25d653cd8f9b05c33c958192c37a90039c21a6c02e` | 772682 |

Sprint 3では以下が同一だった:

```text
flash_standard_slide_001.png == pro_slide_001.png
sha256: abb51af2c42058ea51f5035bc260dfaa3eb00a18cea714ef2787592f3c6bb8c7
```

Sprint 4では `pro_slide_001.png` が別hashになった。  
mode collapseは解消した。

## Before / after metric comparison

| mode | slide | Sprint 3 gate | Sprint 3 min | Sprint 3 small | Sprint 4 gate | Sprint 4 min | Sprint 4 small | Sprint 4 fallback_used |
|---|---:|---|---:|---:|---|---:|---:|---|
| flash_standard | 1 | pass | 22.0 | 0 | pass | 22.0 | 0 | true |
| flash_standard | 2 | fail | 14.4 | 3 | pass | 22.0 | 0 | true |
| pro | 1 | pass | 22.0 | 0 | fail | 14.0 | 4 | false |
| pro | 2 | pass | 22.0 | 0 | fail | 16.0 | 1 | true |

## Telemetry interpretation

両モードとも `fallback_count=1`。  
今回のstage別fallback reasonは両方とも `Strategy generation failed` だった。

重要な発見:

- `fallback_used=true` が残ったslideがある
- しかし telemetry のfallback reasonは strategy fallbackのみ
- つまり、slide HTMLがfallback marker付きになる経路の一部は、まだstage別telemetryに十分出ていない

次は `ensure_text_visible()` や `generate_fallback_html()` を返す経路に、slide単位のfallback reasonを入れると原因追跡が速くなる。

## Vision QA summary

`comparison_contact_sheet.jpg` をvision確認した。

- `pro` は `flash_standard` と明確に別デザインになった
- `pro slide 1` はタイポグラフィ、背景処理、階層がかなり良い
- `pro slide 2` も構図・背景は良い
- ただし `pro` は小さい補助/装飾テキストが増えて、metric上failになった
- `flash_standard slide 2` はpassになったが、見た目はfallback/template感が残る

## Artifacts

Folder:

`docs/qa/results/2026-05-04_design-quality-sprint-4-visible-chrome-regeneration/`

Files:

- `sanitized_api_result.json`
- `artifact_hashes.json`
- `comparison_contact_sheet.jpg`
- `flash_standard_slide_001.png`
- `flash_standard_slide_002.png`
- `pro_slide_001.png`
- `pro_slide_002.png`

## Next actions

1. `ensure_text_visible()` / `generate_fallback_html()` 由来のslide単位fallback reasonをtelemetryに出す
2. `pro` の小さい装飾/補助テキストをquality gateからどう扱うか整理する
   - 実本文ならfail
   - decorative label / footer markerならchrome扱いに寄せる
3. `pro` strategy generationが `Strategy generation failed` になる原因を見る
4. `flash_standard` のfallback/template感を減らす
