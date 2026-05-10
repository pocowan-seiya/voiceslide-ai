# long_japanese_title_wrap_fixture

## 目的

長めの日本語タイトルで、以下を回帰検知するための固定fixture。

- タイトル欠け
- `white-space: nowrap` / `overflow: hidden` / `text-overflow` による省略
- `作 / る`、`スライ / ド` のような1文字分断
- `<br>` が日本語語中へ入った場合の補正

## 代表タイトル

```text
音声からスライド動画を作る流れを確認します
```

## 意図的な悪いHTML断片

```html
<h1 class="title">音声からスライ<br/>ド動画を作<br/>る流れを確認します</h1>
```

期待値:

```text
音声からスライド動画を作る流れを確認します
```

## 対応テスト

```text
backend/tests/test_sprint15_design_quality.py::test_harden_generated_html_typography_repairs_bad_japanese_title_breaks
```
