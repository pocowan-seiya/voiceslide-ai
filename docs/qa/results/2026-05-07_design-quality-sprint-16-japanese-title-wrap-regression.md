# VoiSlide Design Quality Sprint 16 — Japanese title wrap regression

Date: 2026-05-07 15:12 JST

## Scope

Sprint 15 final v2で解消した日本語タイトルの問題を、deterministic regressionとして固定化した。

対象:

- 長めの日本語タイトル
- タイトル内の語中 `<br>`
- `スライ / ド`, `作 / る` のような1文字分断
- タイトル欠け対策の継続確認

## Changes

### Backend

- `backend/services/ai_slide_generator.py`
  - `_repair_bad_japanese_title_breaks(html)` を追加
  - `h1` / `h2` title要素内で、日本語文字同士の間に入った `<br>` を除去
  - `harden_generated_html_typography()` の冒頭でこの補正を実行
  - `font-size` がないHTMLでもタイトル語中 `<br>` 補正は動くようにした

### Tests

- `backend/tests/test_sprint15_design_quality.py`
  - `test_harden_generated_html_typography_repairs_bad_japanese_title_breaks` を追加
  - 悪いHTML例:
    - `音声からスライ<br/>ド動画を作<br/>る流れを確認します`
  - 期待値:
    - `スライド動画`
    - `作る流れ`

### Fixture docs

- `docs/qa/fixtures/long_japanese_title_wrap_fixture.md` を追加
- `docs/qa/fixtures/README.md` に fixture を追記

## Verification

```text
RED:
./venv/bin/python -m pytest tests/test_sprint15_design_quality.py::test_harden_generated_html_typography_repairs_bad_japanese_title_breaks -q
=> 1 failed, 9 warnings

GREEN:
./venv/bin/python -m pytest tests/test_sprint15_design_quality.py::test_harden_generated_html_typography_repairs_bad_japanese_title_breaks -q
=> 1 passed, 9 warnings

Sprint 15 suite:
./venv/bin/python -m pytest tests/test_sprint15_design_quality.py -q
=> 7 passed, 9 warnings

Targeted verification:
./venv/bin/python -m py_compile main.py services/generation_telemetry.py services/design_quality_metrics.py services/ai_utils.py services/openrouter_utils.py services/ai_slide_generator.py && \
./venv/bin/python -m pytest tests/test_design_mode.py tests/test_design_quality_metrics.py tests/test_generation_telemetry.py tests/test_sprint14_design_quality.py tests/test_sprint15_design_quality.py -q
=> 66 passed, 9 warnings

git diff --check
=> pass
```

## Runtime state

```text
port 8001: LISTENなし
port 3010: LISTENなし
port 9223: LISTEN
```

## Notes

- 今回は provider real generation は回していない。
- 理由: Sprint 16は生成品質そのものではなく、Sprint 15で見つかった日本語タイトル1文字分断をdeterministic regressionとして固定化する範囲。
- 共有Chrome/CDP `9223` は従来どおり残した。
