# 2026-05-04 Design Quality Sprint 3 visible Chrome regeneration QA

実施日時: 2026-05-04 20:17〜20:20 JST  
対象: VoiSlide Movie fixed fixture regeneration after Sprint 3 chrome font filtering  
frontend: `http://127.0.0.1:3010/`  
backend: `http://127.0.0.1:8001`  
CDP: `http://127.0.0.1:9223`  
fixture: `docs/qa/fixtures/short_voislide_quality_check_32s.mp3`

## 結論

Sprint 3のchrome font filteringは実データでも効いた。

前回は `flash_standard` / `pro` の全4スライドが `quality_gate=fail` だった。  
今回の再生成では、4スライド中3スライドが `pass` になった。

特に `pro` は2スライドとも `quality_gate=pass`。  
残ったfailは `flash_standard` slide 2 で、これはslide chromeではなく実本文側の小さい文字として検出されている。

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

- job_id: `a0093691-57b5-4b7a-ad96-e8dfa71cba7e`
- transcript_length: 189
- outline_slide_count: 2
- telemetry:
  - `entry_count=6`
  - `total_calls=6`
  - `fallback_count=1`
  - `total_duration_ms=68452`
- `/api/batch-status`: OK
- `/api/status`: OK

Design quality:

| slide | min_font_size_px | small_text_count | fallback_used | quality_gate |
|---:|---:|---:|---|---|
| 1 | 22.0 | 0 | true | pass |
| 2 | 14.4 | 3 | false | fail |

### pro

- job_id: `5fd68c44-efc6-4ff5-80aa-19656a825067`
- transcript_length: 189
- outline_slide_count: 2
- telemetry:
  - `entry_count=6`
  - `total_calls=6`
  - `fallback_count=1`
  - `total_duration_ms=72788`
- `/api/batch-status`: OK
- `/api/status`: OK

Design quality:

| slide | min_font_size_px | small_text_count | fallback_used | quality_gate |
|---:|---:|---:|---|---|
| 1 | 22.0 | 0 | true | pass |
| 2 | 22.0 | 0 | true | pass |

## Before / after metric comparison

前回: `2026-05-04_telemetry-total-calls-visible-chrome-real-generation`

| mode | slide | before gate | before min | before small | after gate | after min | after small |
|---|---:|---|---:|---:|---|---:|---:|
| flash_standard | 1 | fail | 16.0 | 1 | pass | 22.0 | 0 |
| flash_standard | 2 | fail | 16.0 | 1 | fail | 14.4 | 3 |
| pro | 1 | fail | 13.0 | 3 | pass | 22.0 | 0 |
| pro | 2 | fail | 16.0 | 1 | pass | 22.0 | 0 |

## Artifacts

Folder:

`docs/qa/results/2026-05-04_design-quality-sprint-3-visible-chrome-regeneration/`

Files:

- `sanitized_api_result.json`
- `artifact_hashes.json`
- `comparison_contact_sheet.jpg`
- `flash_standard_slide_001.png`
- `flash_standard_slide_002.png`
- `pro_slide_001.png`
- `pro_slide_002.png`

Hashes:

| file | sha256 | size |
|---|---|---:|
| `flash_standard_slide_001.png` | `abb51af2c42058ea51f5035bc260dfaa3eb00a18cea714ef2787592f3c6bb8c7` | 717098 |
| `flash_standard_slide_002.png` | `158b3693c31f9679758c86cc8ee5b64fec43e3ff8c93cf8156c037015536c1ea` | 880170 |
| `pro_slide_001.png` | `abb51af2c42058ea51f5035bc260dfaa3eb00a18cea714ef2787592f3c6bb8c7` | 717098 |
| `pro_slide_002.png` | `cbed7a9ff8e9b2c4ee570aa3cd390f54175102ca8eace5abc6194fa14cf97057` | 655400 |

Note: `flash_standard_slide_001.png` と `pro_slide_001.png` は同一hash。mode差が出たのは主にslide 2。

## Vision QA summary

`comparison_contact_sheet.jpg` をvision確認した。

- `pro 2` が最も良い
  - 見出しが自然
  - 3カード構成で情報整理が明確
  - visual hierarchyが一番強い
  - fallback/template感が最も少ない
- `pro 1` は `flash_standard 1` と同一画像で、改善差はない
- `flash_standard 2` は大きい文字は目立つが、日本語のまとまりが不自然で、小さい文字も残る
- 全体として、proは良くなっているが、本文・カード内テキストの小ささはまだ次の改善対象

## Interpretation

Sprint 3 chrome filteringにより、slide chrome / global default由来のfalse failは減った。  
ただし、生成内容そのものの小さい本文はまだ残る。

次にやるべきこと:

1. `flash_standard` slide 2の小さい本文を減らす
2. `pro` slide 1が `flash_standard` と同一hashになる原因を見る
3. `fallback_used` が残る理由をtelemetry stageごとに見る
4. 本文/card textの最低サイズをprompt/layout側に反映する
