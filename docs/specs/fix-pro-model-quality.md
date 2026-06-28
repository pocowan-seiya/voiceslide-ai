# Fix: Pro モデル使用時のスライド品質低下

## 問題

ユーザーがデフォルトの `Gemini 3 Flash` から `Gemini 3.1 Pro Preview` などの上位モデルに切り替えると、本来は品質が**向上するはず**なのに、実際には**スライドの品質が下がったり、単調になったり**する。

## 根本原因（Explore agent 調査結果）

### 1. `ensure_text_visible()` が高度な CSS を一律削除（最重要）

`backend/services/ai_slide_generator.py` の `ensure_text_visible()` (L2337-2402) に以下の問題：

```python
# 問題: 正しいグラデーションテキスト技法すら破壊
css = re_mod.sub(r'color\s*:\s*transparent', 'color: white', css)
css = re_mod.sub(r'-webkit-background-clip\s*:\s*text\s*;?', '', css)
```

Pro モデルは `background-clip: text` + `-webkit-text-fill-color: transparent` という**正しいグラデーションテキスト技法**を多用するが、これを正規表現で一括削除しているため、Pro の真価が消える。

### 2. タイトル一致チェックが厳格すぎる

L2186, L2393 で `if title not in visible_text:` の素朴な部分一致を使用。
Pro モデルは改行・全角/半角・装飾文字でタイトルを表現することがあり、これが false negative を生み**fallback HTML へフォールバックされる**。

### 3. fallback HTML が単調

`generate_fallback_html()` (L2405-2516) は固定的な flexbox + 絵文字バレットの単調なテンプレート。Pro モデルでフォールバックが頻発する結果、出力が単調になる。

### 4. プロンプトがグラデーションテキストを禁止

`SLIDE_DESIGN_PROMPT` の L1428-1438 で `-webkit-background-clip: text` + `color: transparent` を**絶対禁止**と明記。Pro モデルが得意な技法を封じている。

## 修正方針

### Sprint 1: `ensure_text_visible()` を文脈認識型にする

- `color: transparent` を見つけたら、**同じセレクタブロック内**に有効な `background:` (gradient/color) と `-webkit-background-clip: text` があるか確認
- ある場合 → 正しいグラデーションテキスト → **保持**
- ない場合のみ → 真に不可視 → 修正
- インラインスタイルにも同じロジック

### Sprint 2: タイトル一致チェックを正規化

ヘルパー `_normalize_for_match(text)`:
- 全角/半角統一、空白削除、句読点除去
- 80% 以上の文字が visible_text に含まれていれば一致とみなす
- 完全一致が最優先、それで失敗したら正規化マッチ

### Sprint 3: プロンプト更新

L1428-1438 を以下に置き換え：
- グラデーションテキストは**正しい技法なら推奨**
- 必須セット: `background: linear-gradient(...)` + `-webkit-background-clip: text` + `-webkit-text-fill-color: transparent` + `background-clip: text`
- 上記を**全部揃える**こと、`color: transparent` 単独は禁止

### Sprint 4: fallback HTML 改善

- 戦略色を活かしたランダム要素（grid 配置、サイドバー、ガラスモーフィズム）
- スライド番号によりレイアウト変化（左寄せ/右寄せ/中央）
- グラデーションテキストを使用（fallback でも単調にしない）

## 検証

- `cd backend && python -m pytest tests/ -v`
- `npm run build`
- develop ブランチへ push
