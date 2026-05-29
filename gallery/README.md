# prettyplateau gallery

Every image in this directory is rendered from real PLATEAU data with the
`prettyplateau` CLI. The `gallery_manifest.json` file lists every render
with its city, preset, dimensions, and dataset attribution.

All images carry the mandatory CC BY 4.0 attribution both as visible text
and as file metadata. The originals here are PNG; SVG / PDF variants can
be regenerated with `prettyplateau render … --out file.{png,svg,pdf}`.

## Use Mosaic — per-building usage

| City | Notes |
|---|---|
| ![Shibuya Use Mosaic](shibuya_use_mosaic.png) Shibuya | residential yellow with commercial spines along the Yamanote line |
| ![Minato Use Mosaic](minato_use_mosaic.png) Minato | dense commercial / public mix around Roppongi, Akasaka |
| ![Shinjuku Use Mosaic](shinjuku_use_mosaic.png) Shinjuku | Kabukichō / Yotsuya transition |
| ![Osaka Use Mosaic](osaka_use_mosaic.png) Osaka | full prefecture (615k buildings) |
| ![Kamakura Use Mosaic](kamakura_use_mosaic.png) Kamakura | mixed coastal grain |

## Height Topo — buildings as a topographic ramp

| City | Notes |
|---|---|
| ![Minato Height](minato_height_topo.png) Minato | Roppongi Hills / Akasaka tower cluster |
| ![Shinjuku Height](shinjuku_height_topo.png) Shinjuku | West-Shinjuku skyscrapers vs north residential |
| ![Chiyoda Height](chiyoda_height_topo.png) Chiyoda | Marunouchi / Otemachi |

## Flood Depth — per-building river-flood depth

The hashed grey swatch always means **no data**, never "low risk".

| City | Notes |
|---|---|
| ![Shibuya Flood](shibuya_flood_depth.png) Shibuya | the Shibuya River valley reads as an orange band |
| ![Kōtō Flood](koto_flood_depth.png) Kōtō | Tokyo Bay reclaimed land |
| ![Edogawa Flood](edogawa_flood_depth.png) Edogawa | mostly inside the 5–10 m flood band — the Edogawa / Arakawa basin |

## Risk Choropleth — pre-1981 wood × flood depth (plan flagship)

The plan's flagship intersection: era × structure × hazard, per building.
Where the three inputs aren't all present, the building stays `no_data` —
never inferred. Tokyo wards currently lack `structure` and `year_built`,
so they correctly dominate with the hashed-grey no-data swatch (a truthful
output, not a bug).

| City | Notes |
|---|---|
| ![Kōtō Risk](koto_risk_choropleth.png) Kōtō | mostly no-data (structure + year_built both 0% upstream) |
| ![Edogawa Risk](edogawa_risk_choropleth.png) Edogawa | same caveat; only buildings with all three inputs render in colour |

## Wood Survivor — wood-frame buildings highlighted by era

In Tokyo wards the `structure` column is sparse; the preset falls back to
`fire_resistance` (`準耐火造`, `木造`) to pick out the wood-frame and
quasi-wood-frame buildings that survived the Tokyo firebombings.

| City | Notes |
|---|---|
| ![Shibuya Wood](shibuya_wood_survivor.png) Shibuya | scattered green dots — `準耐火造` buildings |
| ![Taitō Wood](taito_wood_survivor.png) Taitō | Yanaka / Ueno wooden machiya |
| ![Sumida Wood](sumida_wood_survivor.png) Sumida | shitamachi grain |
| ![Kamakura Wood](kamakura_wood_survivor.png) Kamakura | full structure coverage; the canonical wood preset sample |

## Building Age Rainbow — every building by `year_built`

| City | Notes |
|---|---|
| ![Fukuoka Age](fukuoka_age_rainbow.png) Fukuoka | sentinel-corrected year-built; small but truthful coverage |
| ![Sapporo Age](sapporo_age_rainbow.png) Sapporo | one of two cities with full year_built coverage |

## Compound Risk — pre-1981 wood × flood depth (flagship v2 preset)

The intersection of three PLATEAU columns no other public dataset
exposes per-building. Where the data supports it, the headline red
swatch is the textbook worst-case bucket.

| City | Notes |
|---|---|
| ![Kōtō Compound](koto_compound_risk.png) Kōtō | Tokyo Bay reclaimed land combined with shitamachi pre-1981 wood |
| ![Edogawa Compound](edogawa_compound_risk.png) Edogawa | low-lying basin between the two rivers |

## Hazard Confluence — count of overlapping hazards

`zero` is light; `3+ hazards` is deep red. `no_data` is hashed grey.

| City | Notes |
|---|---|
| ![Ōta Hazard](ota_hazard_confluence.png) Ōta | south Tokyo, river × landslide overlap |
| ![Setagaya Hazard](setagaya_hazard_confluence.png) Setagaya | Tama river edge |

## Density Hex — building count aggregated to 250 m hex cells

| City | Notes |
|---|---|
| ![Shinjuku Density](shinjuku_density_hex.png) Shinjuku | density spike right on the station |
| ![Osaka Density](osaka_density_hex.png) Osaka | full prefecture density texture |
| ![Yokohama Density](yokohama_density_hex.png) Yokohama | 880k buildings; whole prefecture |
| ![Nagoya Density](nagoya_density_hex.png) Nagoya | 737k buildings; central commercial spine is the dark band |

Density-hex has the lowest-cost render path (centroid aggregation, O(N) — no
per-polygon work), so it's the right preset for the largest PLATEAU cities.

## Zoning Mosaic — 用途地域

| City | Notes |
|---|---|
| ![Shibuya Zoning](shibuya_zoning_mosaic.png) Shibuya | residential / near-commercial / commercial corridors |
| ![Chiyoda Zoning](chiyoda_zoning_mosaic.png) Chiyoda | almost entirely 商業地域 |

## Survivor Timeline — animation

[`fukuoka_survivor_timeline.mp4`](fukuoka_survivor_timeline.mp4)

180-frame reveal at 3 fps (60-second mp4 per plan-prettyplateau). Buildings
appear in order of recorded `year_built`. The bottom event-year strip
highlights 1923 (Great Kantō), 1945, 1964 (Olympics), 1981 (shin-taishin),
**1990 (bubble peak)**, 2011 (Tōhoku) as the current frame passes each.

The mp4 carries:
- a per-frame caption ("buildings currently in PLATEAU … demolished
  structures are absent by definition") rendered into every figure;
- a 2-second still attribution card at the end;
- container-level attribution metadata.

All three are enforced by `VideoExporter.write_frames` — passing
`attribution_card=None` or a metadata blob without "PLATEAU" raises
`AttributionError` before any bytes hit disk.
