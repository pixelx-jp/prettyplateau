<div align="center">

<img src="https://raw.githubusercontent.com/pixelx-jp/prettyplateau/main/docs/assets/branding/yodo-labs-logo.svg" alt="Yodo Labs" width="120" />

# prettyplateau

**[Project PLATEAU](https://www.mlit.go.jp/plateau/) のデータから、印刷品質の都市可視化を生成する Python ライブラリ。**

[English](./README.md) · [日本語](./README.ja.md)

[![PyPI](https://img.shields.io/pypi/v/prettyplateau.svg)](https://pypi.org/project/prettyplateau/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-orange.svg)](https://creativecommons.org/licenses/by/4.0/)

</div>

---

<img src="https://raw.githubusercontent.com/pixelx-jp/prettyplateau/main/gallery/shibuya_use_mosaic.png" alt="渋谷 — Use Mosaic、prettyplateau で生成" />

```bash
pip install prettyplateau
prettyplateau render --city shibuya --preset use_mosaic --out shibuya.png
```

```python
from prettyplateau import render

render(city="fukuoka", preset="age_rainbow", out="fukuoka.png")
```

> 上のコマンドを動かすには、[`plateau-bridge`](https://github.com/pixelx-jp/plateau-bridge) が生成する
> `out_<city>/buildings.parquet` がローカルに必要です。入手方法は [§ データ](#データ) を参照してください。

## これは何

Project PLATEAU は国土交通省が CC BY 4.0 で公開している全国 3D 都市データです（56 都市以上）。
1 棟ごとに「建築年」「構造」「用途」「災害リスク」といった属性が紐づいており、
OpenStreetMap だけでは作れない種類の地図素材になります。
`prettyplateau` はその属性をポスター品質のラスター／ベクター／動画に焼き付ける、純粋なレンダリング層です。

|  |  |
|---|---|
| <img src="https://raw.githubusercontent.com/pixelx-jp/prettyplateau/main/gallery/minato_height_topo.png" /> | **Height Topo** — 港区の街並みを建物高度の等高線として表示。 |
| <img src="https://raw.githubusercontent.com/pixelx-jp/prettyplateau/main/gallery/koto_flood_depth.png" /> | **Flood Depth** — 江東区の建物ごとの河川洪水浸水深。データなしは斜線グレー（「低リスク」とは別物）。 |
| <img src="https://raw.githubusercontent.com/pixelx-jp/prettyplateau/main/gallery/shinjuku_density_hex.png" /> | **Density Hex** — 新宿駅前を 250 m ヘックスで密度可視化。 |
| <img src="https://raw.githubusercontent.com/pixelx-jp/prettyplateau/main/gallery/fukuoka_age_rainbow.png" /> | **Building Age Rainbow** — 福岡を建築年で色分け。建築年不明の建物は灰色のまま — 推測しません。 |

35 枚の launch ギャラリーは [`gallery/`](./gallery/) をご覧ください。

## 同梱プリセット

| id | 種別 | 必須フィールド | 向いている都市 |
|---|---|---|---|
| `use_mosaic` | 静止画 | `usage` | ほぼ全都市 |
| `height_topo` | 静止画 | `height` | 都心部・大阪市中央 |
| `flood_depth` | 静止画 | `river_flood_*` | 河川沿いの区市町村 |
| `risk_choropleth` | 静止画 | 木造 × 1981年以前 × 浸水深 | プラン本命の重ね合わせ |
| `wood_survivor` | 静止画 | `structure` + `fire_resistance` フォールバック | 台東・墨田・鎌倉 |
| `age_rainbow` | 静止画 | `year_built` | 福岡・札幌 |
| `hazard_confluence` | 静止画 | 複数ハザードの重なり | 多ハザード被覆のある区 |
| `density_hex` | 静止画 | 重心 → ヘックス格子 | 全都市対応・大規模都市向け |
| `zoning_mosaic` | 静止画 | `zoning_use`（用途地域） | 東京・大阪 |
| `survivor_timeline` | mp4 (60秒) | `year_built` | 福岡・札幌 |

> PLATEAU の属性カバー率は都市ごとに異なります。`prettyplateau` は欠損データを **`unknown`**
> として明示的に灰色で表示し、決して暗黙裡に補完しません。テーマで色を上書きすることもできません。

## テーマ

```bash
prettyplateau render --city shibuya --preset use_mosaic --theme sakura --out shibuya.png
```

`default` · `print` · `sakura` · `summer_matsuri` · `snow` · `neon_night`

テーマは背景色、コントラスト、紙質感などの「見え方」のみを変えます。
意味論（`unknown`／`no_data`／ハザード重大度の順序）は preset 側で固定されており、
テーマからは変更できません — これはコードレベルで強制されています。

## マルチフォーマット出力

```bash
# 1 回のデータ読み込みで 3 形式同時出力：
prettyplateau render --city shibuya --preset use_mosaic \
  --out 'shibuya.{png,svg,pdf}' --sidecar
```

| 形式 | 用途 |
|---|---|
| PNG (4K) | SNS・ポスター |
| SVG | Illustrator 加工用 |
| PDF (300 dpi) | 印刷入稿 |
| mp4 (H.264) | アニメーション preset |

`--sidecar` を付けると `{出力名}.json` に request 全体と preset メタデータが
書き出され、後から再現が可能になります。

## カスタムプリセット

```bash
prettyplateau create-preset my-preset --name "My Preset"
cd prettyplateau_preset_my_preset
pip install -e .
pytest    # 最初から緑
```

サードパーティ製 preset は Python の entry point（`prettyplateau.presets`
グループ）で登録します。スキャフォルドコマンドは
preset 本体・カラーパレット JSON・スモークテスト・pyproject.toml までを一括生成します。

## クレジット表記（Attribution）

生成された PNG / SVG / PDF / mp4 にはすべて次の文字列が埋め込まれます：

```
© Project PLATEAU / MLIT (CC BY 4.0) · {dataset_id} · {生成日}
```

可視テキスト **かつ** ファイルメタデータの両方として、必ず焼き付けられます。
無効化フラグは存在せず、テーマでも隠せず、独自ロゴで覆い隠すこともできません。
これは PLATEAU データの CC BY 4.0 ライセンスの帰結です。
詳細は [`NOTICE.md`](./NOTICE.md) を参照してください。

## データ

prettyplateau は **PLATEAU データを再配布しません**。
[plateau-bridge](https://github.com/pixelx-jp/plateau-bridge) が生成する
`buildings.parquet` を読み込みます。データ入手は次の 3 通り：

### 方法 1 — plateau-bridge を自分で動かす（56 都市以上から自由に選択）

```bash
git clone https://github.com/pixelx-jp/plateau-bridge && cd plateau-bridge
pip install -e .
plateau pipeline --city shibuya --out out_shibuya
prettyplateau render --city shibuya --preset use_mosaic \
  --out shibuya.png --data-root /path/to/plateau-bridge
```

### 方法 2 — Hugging Face Datasets でサンプル parquet を入手（予定）

需要の多い都市について、Hugging Face Datasets にビルド済み parquet を
ホスティングする予定です（v0.2 で着手予定）。

### 方法 3 — 独自の GeoDataFrame を渡す

`prettyplateau.data.access.CityDataset` を直接構築して preset に渡せます。
具体例は `examples/custom_preset.py` をご覧ください。

### ライセンス

PLATEAU データは国土交通省による **CC BY 4.0** で提供されています。
`prettyplateau` の出力を公開する際は、画像上の可視 attribution と
ファイル内メタデータの両方がそろっていることでライセンス条件を満たします。
**attribution を切り取って公開しないでください** — ライセンス違反になります。

## パフォーマンス

Apple M シリーズでのレンダリング時間：

| 都市 | 建物数 | 2400 px PNG |
|---|---|---|
| 渋谷 | 4.2 万 | 18 秒 |
| 港 | 3.2 万 | 27 秒 |
| 福岡 | 35.5 万 | 120 秒 |
| 大阪 | 61.5 万 | 230 秒 |
| 横浜 | 88 万 | 約 330 秒（density_hex のみ） |

アニメーション：60 秒の福岡 `survivor_timeline.mp4`（180 フレーム × 3 fps）
で 5 分 40 秒程度。プロファイル結果と v0.2 で見込まれる 4〜5 倍高速化の方針は
[`distribution/perf_notes.md`](./distribution/perf_notes.md) に整理しています。

## ステータス

`0.1.0` — 初回公開リリースです。変更履歴は [`CHANGELOG.md`](./CHANGELOG.md) を参照してください。

## コントリビューション

バグ報告、preset の PR、テーマ PR、地名翻訳 PR、いずれも歓迎します。
PR を出される前に [`CONTRIBUTING.md`](./CONTRIBUTING.md) のアーキテクチャ
不変条件をご一読ください（特に「attribution を無効化できない」という設計は妥協できません）。

## ライセンス

- **コード**：MIT（[`LICENSE`](./LICENSE)）
- **同梱フォント**：SIL Open Font License 1.1（Noto Sans CJK JP + Inter）
- **生成物**：可視テキストとファイルメタデータの両方に PLATEAU の CC BY 4.0 attribution
- **第三者表記の索引**：[`NOTICE.md`](./NOTICE.md)

---

<div align="center">

**[Yodo Labs](https://yodolabs.jp)**（ピクセルエックス株式会社 / PixelX Inc.）東京
<br/>
お問い合わせ・パートナーシップ：[pan@yodolabs.jp](mailto:pan@yodolabs.jp)

</div>
