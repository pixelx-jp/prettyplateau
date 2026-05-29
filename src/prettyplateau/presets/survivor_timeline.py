"""Surviving Buildings Timeline — animated reveal of currently-standing buildings.

Important framing: this is NOT a city growth animation. It shows **buildings
that exist in the PLATEAU dataset today, revealed in order of their recorded
build year.** Buildings that were demolished are not in the dataset, so they
never appear in the timeline. The preset's caption makes that explicit and the
animator embeds it in every frame.

Frames:
  - 30 frames spanning the data range (defaults: from min(year_built) to current year).
  - Each frame shows: building with year <= t in age_rainbow colours; year > t in
    near-background tint; year unknown in grey throughout (constant overlay).
  - Event markers: 1923 (Great Kanto Earthquake), 1945, 1964 (Olympics), 1981
    (shin-taishin), 2011 (Tohoku). The frame whose year crosses each marker
    gets the annotation appended to its label.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.data.access import CityDataset
from prettyplateau.data.schema import COL_YEAR_BUILT
from prettyplateau.presets._common import AGE_BUCKETS, assign_age_keys, bbox_of_gdf
from prettyplateau.presets._layers import admin_boundary_layer
from prettyplateau.presets.base import BasePreset, PreparedData, TimelineFrame, TimelineSpec
from prettyplateau.presets.scene import (
    LegendEntry,
    LegendSpec,
    PolygonLayer,
    RenderScene,
    TextAnnotation,
)
from prettyplateau.style.palette import apply_theme_overrides, load_palette
from prettyplateau.style.theme import Theme

# Event markers per plan-prettyplateau.md (Surviving Buildings Timeline):
# 1923 · Kantō / 1945 · WWII end / 1964 · Olympics / 1990 · Bubble peak /
# 2011 · Tōhoku. 1981 is included as a non-plan addition because the
# shin-taishin building code revision is the single most consequential
# date for Japanese building stock — but it's optional from the plan's
# perspective.
_EVENT_MARKERS: dict[int, str] = {
    1923: "1923 · Great Kantō earthquake",
    1945: "1945 · End of WWII",
    1964: "1964 · Tokyo Olympics",
    1981: "1981 · shin-taishin building code",
    1990: "1990 · Bubble economy peak",
    2011: "2011 · Tōhoku earthquake",
}


def _faded(color: str, alpha: float = 0.06) -> str:
    """Mix toward white. Used for not-yet-revealed buildings."""
    # Simple linear mix in sRGB. Approximate but cheap.
    c = color.lstrip("#")
    r, g, b = (int(c[i : i + 2], 16) for i in (0, 2, 4))
    r = int(r * alpha + 255 * (1 - alpha))
    g = int(g * alpha + 255 * (1 - alpha))
    b = int(b * alpha + 255 * (1 - alpha))
    return f"#{r:02X}{g:02X}{b:02X}"


class SurvivorTimelinePreset(BasePreset):
    metadata = PresetMetadata(
        id="survivor_timeline",
        name="Surviving Buildings Timeline",
        description="Animated reveal of buildings currently in PLATEAU, ordered by year built.",
        modes=["animation"],
        required_fields=[COL_YEAR_BUILT],
        default_format="mp4",
    )

    def prepare(self, dataset: CityDataset, request: RenderRequest) -> PreparedData:
        gdf = dataset.gdf
        # mp4 render time scales O(frames × buildings); offer an opt-in cap so
        # mega-cities can ship a watchable preview in minutes, not hours.
        max_buildings = int(request.options.get("max_buildings", 0))
        if max_buildings and len(gdf) > max_buildings:
            gdf = gdf.sample(n=max_buildings, random_state=42).reset_index(drop=True)
            dataset = CityDataset(
                city=dataset.city,
                city_name=dataset.city_name,
                city_code=dataset.city_code,
                dataset_year=dataset.dataset_year,
                dataset_id=dataset.dataset_id,
                attribution=dataset.attribution,
                field_coverage=dataset.field_coverage,
                n_buildings=len(gdf),
                gdf=gdf,
                source_root=dataset.source_root,
                extras=dataset.extras,
            )
        if COL_YEAR_BUILT not in gdf.columns:
            keys = pd.Series(["unknown"] * len(gdf), index=gdf.index)
            return PreparedData(
                dataset=dataset,
                derived={"age_keys": keys, "years": pd.Series(np.nan, index=gdf.index)},
                warnings=(f"city {dataset.city!r} has no year_built; timeline will be a single static frame.",),
            )
        years = pd.to_numeric(gdf[COL_YEAR_BUILT], errors="coerce")
        age_keys = assign_age_keys(years)
        coverage = dataset.field_coverage.get("year_built", 0.0)
        warnings = ()
        if coverage < 0.5:
            warnings = (
                f"year_built coverage is {coverage:.0%} for {dataset.city!r}; "
                "most buildings will remain grey throughout the timeline.",
            )
        return PreparedData(dataset=dataset, derived={"age_keys": age_keys, "years": years}, warnings=warnings)

    def build_timeline(self, prepared: PreparedData, theme: Theme, request: RenderRequest) -> TimelineSpec | None:
        ds = prepared.dataset
        gdf = ds.gdf
        years: pd.Series = prepared.derived["years"]
        age_keys: pd.Series = prepared.derived["age_keys"]
        palette = apply_theme_overrides(load_palette("age_rainbow"), theme)

        # Choose frame years. Strip out plateau-bridge's `year_built = 1`
        # sentinels and anything older than 1850 before computing the range —
        # otherwise the timeline wastes 70%+ of its frames on pre-Meiji years
        # where no real building exists in PLATEAU.
        #
        # Default 180 frames at 3 fps = 60 seconds, matching the plan-defined
        # "60 秒 mp4" length. Callers can override via -O frames/-O fps.
        n_frames = int(request.options.get("frames", 180))
        fps = int(request.options.get("fps", 3))
        plausible = years.dropna()
        plausible = plausible[plausible >= 1850]
        if plausible.empty:
            year_grid: Iterable[int] = [pd.Timestamp.utcnow().year]
        else:
            y_lo = int(plausible.quantile(0.01))
            y_hi = int(min(plausible.quantile(0.999), 2030))
            year_grid = np.linspace(y_lo, y_hi, n_frames).astype(int).tolist()

        geometries = list(gdf.geometry)
        [palette.color_for(k) for k in age_keys.tolist()]
        unknown_mask = age_keys == "unknown"
        [palette.color_for("unknown") if u else None for u in unknown_mask.tolist()]
        # Pre-compute faded versions per palette key.
        faded_by_key = {k: _faded(palette.color_for(k)) for k in palette.colors}

        frames: list[TimelineFrame] = []
        bounds = bbox_of_gdf(gdf)
        years_arr = years.to_numpy(dtype=float)
        keys_arr = age_keys.to_numpy()
        boundary_layer = admin_boundary_layer(ds, theme)
        year_lo, year_hi = (int(year_grid[0]), int(year_grid[-1])) if year_grid else (0, 0)

        legend = LegendSpec(
            title="Year built",
            entries=tuple(
                LegendEntry(label=label, color=palette.color_for(key))
                for _, _, key, label in AGE_BUCKETS
            )
            + (
                LegendEntry(label="Unknown / no data", color=palette.color_for("unknown"), is_no_data=True),
            ),
            note="Only buildings currently in PLATEAU are shown — demolished structures are not in the data.",
        )

        for fi, target_year in enumerate(year_grid):
            fills: list[str] = []
            frame_keys: list[str] = []
            for i in range(len(geometries)):
                yr = years_arr[i]
                if np.isnan(yr):
                    fills.append(palette.color_for("unknown"))
                    frame_keys.append("unknown")  # reserved — never tinted by theme contrast
                elif yr <= target_year:
                    fills.append(palette.color_for(keys_arr[i]))
                    frame_keys.append(str(keys_arr[i]))
                else:
                    fills.append(faded_by_key.get(keys_arr[i], palette.color_for("unknown")))
                    # Faded fill is a derived colour, not a palette key — leave
                    # it empty so the renderer is free to apply theme contrast.
                    frame_keys.append("")
            layer = PolygonLayer(
                id="buildings",
                geometries=geometries,
                fills=fills,
                fill_keys=frame_keys,
                z=10,
                semantic={"field": "year_built", "frame_year": int(target_year)},
            )
            event_suffix = _EVENT_MARKERS.get(int(target_year), "")
            label = f"≤ {int(target_year)}" + (f"  ·  {event_suffix}" if event_suffix else "")
            annotations = self._build_annotations(
                target_year=int(target_year),
                year_lo=year_lo,
                year_hi=year_hi,
                theme=theme,
            )
            layers_for_frame = (boundary_layer, layer) if boundary_layer else (layer,)
            scene = RenderScene(
                bounds=bounds,
                background=theme.background,
                layers=layers_for_frame,
                legend=legend,
                annotations=annotations,
                semantic_metadata={
                    "preset": self.metadata.id,
                    "frame_year": int(target_year),
                },
            )
            t = fi / max(len(year_grid) - 1, 1)
            frames.append(TimelineFrame(t=t, label=label, scene=scene))

        return TimelineSpec(
            duration_seconds=len(frames) / max(fps, 1),
            fps=fps,
            frames=tuple(frames),
            caption=(
                "Surviving Buildings Timeline — buildings currently in PLATEAU, "
                "revealed in order of recorded build year. Demolished structures "
                "are absent by definition."
            ),
        )

    def build_scene(self, prepared: PreparedData, theme: Theme, request: RenderRequest) -> RenderScene:
        # Fallback for static export of an animation preset: render the final frame.
        timeline = self.build_timeline(prepared, theme, request)
        if timeline and timeline.frames:
            return timeline.frames[-1].scene
        # Degenerate case: no year data — return a uniform grey scene.
        ds = prepared.dataset
        gdf = ds.gdf
        palette = apply_theme_overrides(load_palette("age_rainbow"), theme)
        fills = [palette.color_for("unknown")] * len(gdf)
        return RenderScene(
            bounds=bbox_of_gdf(gdf),
            background=theme.background,
            layers=(
                PolygonLayer(
                    id="buildings",
                    geometries=list(gdf.geometry),
                    fills=fills,
                    fill_keys=["unknown"] * len(gdf),
                    z=10,
                ),
            ),
            legend=None,
        )

    @staticmethod
    def _build_annotations(
        *,
        target_year: int,
        year_lo: int,
        year_hi: int,
        theme: Theme,
    ) -> tuple[TextAnnotation, ...]:
        """Bottom timeline strip showing year markers and the current year.

        Drawn as figure-fraction TextAnnotations so the animator's persistent
        canvas doesn't need to know about year-line geometry.
        """
        annotations: list[TextAnnotation] = []
        span = max(year_hi - year_lo, 1)
        # Strip lives just above the legend band (~y=0.15).
        strip_y = 0.155
        # Tick marks at each event year that falls within the data range.
        for ev_year, _ev_label in _EVENT_MARKERS.items():
            if not (year_lo <= ev_year <= year_hi):
                continue
            x = 0.06 + (ev_year - year_lo) / span * 0.88
            is_current = ev_year <= target_year
            annotations.append(
                TextAnnotation(
                    text=f"│  {ev_year}",
                    x=x,
                    y=strip_y,
                    align="left",
                    valign="bottom",
                    color=theme.foreground if is_current else theme.muted,
                    size=7.0,
                    weight="medium" if is_current else "regular",
                    z=9_500,
                )
            )
        # Current-year callout, anchored to the right edge of the strip.
        annotations.append(
            TextAnnotation(
                text=f"current year: {target_year}",
                x=0.94,
                y=strip_y + 0.012,
                align="right",
                valign="bottom",
                color=theme.accent,
                size=10.0,
                weight="bold",
                z=9_600,
            )
        )
        return tuple(annotations)


PRESET = SurvivorTimelinePreset()


def factory() -> SurvivorTimelinePreset:
    return SurvivorTimelinePreset()
