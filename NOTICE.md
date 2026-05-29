# Third-party notices

`prettyplateau` is © 2026 Yodo Labs (PixelX Inc. / ピクセルエックス株式会社),
MIT-licensed (see `LICENSE`). It bundles two font families and operates on
PLATEAU data; this file documents the third-party obligations each of those
carries.

## Bundled fonts

Both fonts are redistributed verbatim inside the wheel under
`prettyplateau/fonts/assets/`. Their licenses are also in the wheel at
`prettyplateau/fonts/assets/licenses/`.

### Noto Sans CJK JP (Regular)

- File: `src/prettyplateau/fonts/assets/NotoSansJP-Regular.otf`
- Source: <https://github.com/notofonts/noto-cjk>
- License: SIL Open Font License, Version 1.1
- License file:
  `src/prettyplateau/fonts/assets/licenses/NotoSansCJK-LICENSE.txt`

### Inter (Regular + SemiBold)

- Files:
  - `src/prettyplateau/fonts/assets/Inter-Regular.otf`
  - `src/prettyplateau/fonts/assets/Inter-SemiBold.otf`
- Source: <https://github.com/rsms/inter>, v4.1
- License: SIL Open Font License, Version 1.1
- License file:
  `src/prettyplateau/fonts/assets/licenses/Inter-LICENSE.txt`

Both fonts may be embedded into prettyplateau-generated PDFs / SVGs without
extra permission, per the OFL.

## PLATEAU data

prettyplateau does **not** redistribute PLATEAU data. It reads
`buildings.parquet` files produced by
[plateau-bridge](https://github.com/pixelx-jp/plateau-bridge) (sibling
project) which in turn derives from the public PLATEAU dataset.

- Source data: <https://www.geospatial.jp/ckan/dataset/plateau>
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)
- Attribution text (embedded in every artifact):
  `© Project PLATEAU / MLIT (CC BY 4.0)`
- Per-artifact embedding:
  - PNG: `tEXt`/`iTXt` chunks AND visible corner text
  - SVG: `<dc:Attribution>` metadata AND visible `<text>`
  - PDF: document-info `Subject` AND visible text
  - mp4: container metadata (`comment`, `copyright`) AND a mandatory
    2-second end card frame
- Attribution removal is enforced as impossible at the exporter layer
  (see `compose/attribution_injector.py` and
  `export/video.py::write_frames`); there is no public flag to disable it.

When you publish an image rendered by prettyplateau, the visible
attribution + file-metadata attribution together satisfy CC BY 4.0
attribution. **Do not** crop the attribution out before publishing — that
breaks the licence.

## Administrative boundary geojson

The city silhouette layer reads `data/japan_admin.geojson` from
`plateau-bridge`. Per that project's NOTICE: the Tokyo subset is from
`dataofjapan/land` (MIT) and the rest is derived from MLIT's 国土数値情報
N03 行政区域 (2024) under their open-data terms.
