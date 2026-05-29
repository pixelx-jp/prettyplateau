# Render performance notes

cProfile on `prettyplateau render --city shibuya --preset use_mosaic` at width=1200.
Shibuya has 41,829 buildings which decompose into **459,201 polygon rings**
(MultiPolygons + interior holes), so per-ring overhead dominates everything.

## Where 42 seconds go

| Stage | Cumulative time | % of total | Bottleneck |
|---|---|---|---|
| `MatplotlibRenderer.render` | 38.95 s | 92% | parent of everything below |
| `_draw_polygon_layer` | 38.08 s | 90% | calls `_geom_to_patches` per geometry |
| `_geom_to_patches` (41,830 calls) | 33.88 s | 80% | calls `_polygon_to_path` 459k times |
| `_polygon_to_path` (459k calls) | 15.45 s | 36% | shapely coord iter + matplotlib Path build |
| `PathPatch.__init__` (459k allocs) | 15.35 s | 36% | one Python object per ring |
| matplotlib `colors.to_rgba` (2.75M calls) | 8.00 s | 19% | per-patch facecolor resolution |
| Shapely `.coords` iter | 5.72 s | 14% | reading ring coords one polygon at a time |
| Matplotlib draw (PatchCollection.draw) | 1.79 s | 4% | the actual rasterisation is fast |

**Punch line: the actual drawing is only 4% — the other 96% is Python object
churn building up to it.**

## Next optimisation (4-5× speedup potential)

**Replace `PathPatch` per ring with a single `Path` built from numpy arrays.**

Plan:

1. `shapely.get_coordinates(geoms, return_index=True)` → one numpy array of
   all (x, y) + a ring-index array, in a single C call (~50 ms for 41k geoms).
2. Compute ring-start offsets via `np.unique(ring_index, return_counts=True)`.
3. Build one vectorised `codes` array with MOVETO at each ring start and
   CLOSEPOLY at each ring end.
4. One `matplotlib.path.Path(verts, codes)` + one `PathCollection` — no
   per-ring Python objects.

Expected impact:
- 36% × 459k `PathPatch` allocs → ~0 → **~15 s saved**
- 36% × `_polygon_to_path` Python loop → vectorised → **~12 s saved**
- 19% × per-patch `to_rgba` normalisation → resolved once → **~6 s saved**

→ Shibuya 42 s → **~9-10 s**.
→ Osaka 230 s → **~50 s**.
→ Fukuoka 120 s → **~25 s**.

## Why this is v0.2 not v0.1

1. Risk: rewrites the most-tested module. Visual baselines + launch gallery
   need re-rendering.
2. Animator `update_layer_fills` uses `PatchCollection.facecolors`. The
   `PathCollection` API is similar but every preset would re-verify.
3. Not blocking launch — 42 s / Shibuya is fine for a one-shot poster. Bigger
   cities are slow but tolerable.

**Recommendation:** ship v0.1.0 as-is. File `feat/path-collection-rewrite`
as the headline perf issue for v0.2.

## What's already optimised (v0.1.0)

- `PatchCollection` batch path → ~30× speedup over `ax.add_patch` per polygon.
- Persistent canvas + per-frame fill-only updates for animations →
  12-frame Fukuoka mp4: 287 s → 54 s (5.3×). 60-frame timeline: ~5:40.
- Centroid-bbox prefilter on `load_buildings` skips out-of-frame polygons.
- Theme contrast vectorised, not per-patch.

So we're not at zero — the easy wins are in. The remaining 4-5× needs the
rewrite above.
