# VoiSlide Design Quality Sprint 26 — Browser Occupancy Override

日時: 2026-05-08

## 結論

Sprint 26として、HTML/CSS静的metricが小さい装飾要素を主役要素として誤検出した場合に、browser computed layoutの実測値で上書きできるようにした。

Sprint 25後に残っていた `pro` slide 1 の main occupancy warning は解消した。

`flash_standard` slide 2 は、主役コンテナが存在せず、title単体の面積も0.30未満のため、現時点では実質的なdensity warningとして残した。

## 原因

`analyze_design_quality_with_browser_layout()` は、静的metricで `main_element_occupancy_ratio` が `None` の場合だけbrowser metricを使っていた。

そのため、静的解析が小さい装飾要素を拾って `0.000xxx` のような値を返すと、browser computed layoutの正しい主役コンテンツ面積に進めなかった。

## 実装

対象:

- `backend/services/design_quality_metrics.py`

変更:

- 静的occupancyが `None` の場合だけでなく、`_MAIN_OCCUPANCY_MIN` 未満の場合もbrowser metricを実行する。
- browser metricが静的metricより大きい場合は、browser側の値で上書きする。
- 上書き後に閾値を満たす場合は、古い `主役要素の画面占有率` warningを削除する。
- title clipping detectorの縦方向判定に小さな描画丸め誤差のtoleranceを追加する。
- Sprint 25 final typography hardeningの `line-height: 1.3` 補正でセミコロンが欠けるケースを修正した。

## 追加テスト

対象:

- `backend/tests/test_design_quality_metrics.py`

追加:

- `test_browser_layout_overrides_tiny_static_decorative_occupancy_with_real_content`

確認内容:

- 静的metricが小さい装飾要素を拾って `0.01` 未満になる。
- browser metricでは実コンテンツ `.content` を測定する。
- browser側の占有率が `0.30` 以上なら `pass` になる。

## Sprint 23 artifact再適用

保存先:

```text
docs/qa/results/2026-05-08_sprint23_real-generation-metrics-qa/sprint26_fixed_condition_occupancy_measurements.json
```

結果:

| mode | slide | gate | occupancy | title_clipping | title_font |
|---|---:|---|---:|---:|---:|
| flash_standard | 1 | pass | 0.589737 | false | 72px |
| flash_standard | 2 | warn | 0.000868 | false | 72px |
| pro | 1 | pass | 0.723775 | false | 72px |
| pro | 2 | pass | 1.0 | false | 82px |

## 残したwarning

`flash_standard` slide 2のみ、main occupancy warningを残した。

理由:

- browser candidateになる主役コンテナがない。
- title単体の面積も0.30未満。
- screenshot visual-density metricでは過検出しない水準だが、HTML/layout metric上は「主役要素が小さい」判定として妥当。

これはmetricバグではなく、`flash_standard`のtitle-only slide設計をどう扱うかの仕様判断になる。

## Verification

- `py_compile`: pass
- `tests/test_design_quality_metrics.py tests/test_sprint15_design_quality.py`: 51 passed, 9 warnings
- targeted verification: 86 passed, 9 warnings
- `git diff --check`: pass

## 次の候補

Sprint 27では、`flash_standard` の title-only slide を以下のどちらで扱うか決める。

1. title-only slideのoccupancy閾値を別枠にする。
2. 生成側でtitle-only slideにも明示的な主役コンテナを付与する。

現時点では、2の方が実生成品質に波及しやすい。
