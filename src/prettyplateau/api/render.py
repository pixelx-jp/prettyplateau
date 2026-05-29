"""Top-level render() entry point. CLI and Python users both land here."""

from __future__ import annotations

import datetime as _dt
import time
from pathlib import Path
from typing import Any

from prettyplateau.api.types import OutputFormat, PresetMetadata, RenderRequest, RenderResult
from prettyplateau.compose.attribution_injector import AttributionInjector, AttributionSpec
from prettyplateau.compose.composer import Composer, CompositionOptions
from prettyplateau.core.errors import (
    BBoxEmptyError,
    DataFieldMissingError,
    PresetExecutionError,
)
from prettyplateau.core.logging import get_logger
from prettyplateau.core.metadata import build_artifact_metadata
from prettyplateau.data.access import DataAccess
from prettyplateau.export import exporter_for_format
from prettyplateau.presets.registry import get_registry
from prettyplateau.renderers.matplotlib_renderer import MatplotlibRenderer, RenderOptions
from prettyplateau.style.theme import get_theme

_logger = get_logger("render")


def _camel(key: str) -> str:
    """`n_no_data` → `NNoData`, used to keep artifact metadata keys consistent
    with the PascalCase convention already established for Software /
    Attribution / DatasetID."""
    return "".join(part.capitalize() if part else "" for part in key.split("_"))


_FORMAT_BY_SUFFIX: dict[str, OutputFormat] = {
    ".png": "png",
    ".svg": "svg",
    ".pdf": "pdf",
    ".mp4": "mp4",
}


def _infer_format(request: RenderRequest, preset_default: OutputFormat | None = None) -> OutputFormat:
    """Pick the output format for this render.

    Precedence (per plan-prettyplateau.md "输出格式策略"):
      1. Explicit `request.format` always wins.
      2. Suffix of `request.out`.
      3. The preset's own `default_format` from its metadata.
      4. PNG.

    Step 3 matters for animation presets — `survivor_timeline` declares
    `default_format="mp4"` and would otherwise silently fall back to PNG
    when the caller forgets the suffix.
    """
    if request.format:
        return request.format
    if request.out:
        suffix = Path(request.out).suffix.lower()
        if suffix in _FORMAT_BY_SUFFIX:
            return _FORMAT_BY_SUFFIX[suffix]
    if preset_default is not None:
        return preset_default
    return "png"


def render(
    city: str | None = None,
    preset: str | None = None,
    out: str | None = None,
    *,
    format: OutputFormat | None = None,
    theme: str = "default",
    bbox: tuple[float, float, float, float] | None = None,
    width: int | None = None,
    height: int | None = None,
    dpi: int = 300,
    title: str | None = None,
    subtitle: str | None = None,
    overwrite: bool = False,
    return_scene: bool = False,
    request: RenderRequest | None = None,
    data_root: str | None = None,
    **options: Any,
) -> RenderResult:
    """Render a single PLATEAU visualization.

    Either pass keyword args (`render(city=..., preset=..., out=...)`) or a
    pre-built `RenderRequest`. CLI uses the latter; library users typically use
    kwargs.
    """
    if request is None:
        if city is None or preset is None:
            raise TypeError("render() requires either `request=` or both `city=` and `preset=`")
        request = RenderRequest(
            city=city,
            preset=preset,
            out=out,
            format=format,
            theme=theme,
            bbox=bbox,
            width=width,
            height=height,
            dpi=dpi,
            title=title,
            subtitle=subtitle,
            overwrite=overwrite,
            options=options,
        )
    t0 = time.perf_counter()

    registry = get_registry()
    preset_obj = registry.resolve(request.preset)
    requirement = preset_obj.required_data(request)
    # Format resolution needs the preset's metadata so animation presets
    # default to mp4 instead of silently picking PNG.
    fmt = _infer_format(request, preset_default=preset_obj.metadata.default_format)

    access = DataAccess(data_root=data_root)
    dataset = access.load_city(request.city, bbox=request.bbox)
    if dataset.gdf.empty:
        raise BBoxEmptyError(
            f"city {request.city!r}: no buildings inside the requested bbox / dataset is empty"
        )

    # Required-field check: if a column is *completely* missing from the parquet
    # we fail-fast; if it's just sparsely populated we proceed with warnings.
    missing = [f for f in requirement.required_fields if f not in dataset.gdf.columns]
    if missing:
        raise DataFieldMissingError(field=missing[0], city=request.city)

    try:
        prepared = preset_obj.prepare(dataset, request)
        theme_obj = get_theme(request.theme)
        timeline = None
        if fmt == "mp4" or "animation" in preset_obj.metadata.modes and request.options.get("animate", fmt == "mp4"):
            timeline = preset_obj.build_timeline(prepared, theme_obj, request)
        scene = preset_obj.build_scene(prepared, theme_obj, request)
    except Exception as exc:  # noqa: BLE001
        raise PresetExecutionError(request.preset, exc) from exc

    composition_options = CompositionOptions(
        title=request.title or scene.semantic_metadata.get("preset_title"),
        subtitle=request.subtitle,
        show_legend=True,
        show_attribution=True,
    )
    renderer = MatplotlibRenderer()
    render_opts = RenderOptions(
        width_px=request.width or 3840,
        height_px=request.height,
        dpi=request.dpi,
        background=theme_obj.background,
        top_margin=composition_options.top_margin(),
        bottom_margin=composition_options.bottom_margin(),
        side_margin=composition_options.side_margin(),
    )
    fig = renderer.render(scene, theme_obj, render_opts)

    attribution_text = access.get_attribution(dataset)
    generated_at = _dt.datetime.now(tz=_dt.timezone.utc)
    spec = AttributionSpec(
        text=attribution_text,
        dataset_id=dataset.dataset_id,
        generated_at=generated_at,
    )
    # User-controllable placement (per plan: position is adjustable, never
    # closeable). Other style knobs (size, language) are not exposed at the
    # CLI yet — the defaults are designed to satisfy CC BY 4.0 readability.
    from prettyplateau.compose.attribution_injector import AttributionStyle

    corner_str = request.options.get("attribution_corner", "bottom-right") if request.options else "bottom-right"
    attribution_style = AttributionStyle(corner=corner_str)  # type: ignore[arg-type]
    composer = Composer(AttributionInjector(spec, attribution_style))
    composition = composer.compose(fig, scene, theme_obj, composition_options)

    # Plan: "API 结果 metadata 必须暴露 no-data building 数量". We bubble the
    # full semantic_metadata block (n_buildings, n_unknown, n_no_data,
    # n_headline, n_wood_pre1945, etc.) into the artifact metadata so users
    # can reason about coverage without re-running the preset's prepare step.
    semantic_extra: dict[str, str] = {
        "Bounds": ",".join(f"{v:.6f}" for v in scene.bounds),
    }
    for key, value in scene.semantic_metadata.items():
        if key == "preset":  # already in metadata as "Preset"
            continue
        semantic_extra[_camel(key)] = str(value)
    md = build_artifact_metadata(
        preset_id=request.preset,
        city=dataset.city_name or request.city,
        dataset_id=dataset.dataset_id,
        attribution=attribution_text,
        theme=request.theme,
        generated_at=generated_at,
        extra=semantic_extra,
    )

    # Determine which output paths to write. The CLI may expand a brace
    # pattern like `shibuya.{png,svg,pdf}` into multiple paths and pass them
    # via `request.options["extra_outs"]` so the figure (which is expensive
    # to build) can be reused across formats.
    extra_outs: list[str] = list(request.options.get("extra_outs", [])) if request.options else []
    sidecar_enabled: bool = bool(request.options.get("sidecar", False)) if request.options else False
    out_paths: list[tuple[Path, str]] = []
    if request.out:
        out_paths.append((Path(request.out).expanduser(), fmt))
    for extra in extra_outs:
        ep = Path(extra).expanduser()
        extra_fmt = _FORMAT_BY_SUFFIX.get(ep.suffix.lower(), "png")
        out_paths.append((ep, extra_fmt))

    out_path: Path | None = None
    width_px = height_px = 0
    primary_result = None
    written: list[Path] = []
    for path, this_fmt in out_paths:
        if this_fmt == "mp4":
            if timeline is None:
                raise PresetExecutionError(
                    request.preset, RuntimeError("preset did not produce a timeline; cannot encode mp4")
                )
            from prettyplateau.animation.animator import Animator
            from prettyplateau.export.video import VideoExporter

            attribution_card_rgba = _render_attribution_card(composition)
            animator = Animator(renderer, composer, composer.attribution)
            frames_iter = animator.stream(
                timeline,
                theme_obj,
                render_opts,
                title=request.title,
                subtitle=request.subtitle,
            )
            rgbas = (f.rgba for f in frames_iter)
            video = VideoExporter()
            result = video.write_frames(
                path,
                frames=rgbas,
                fps=timeline.fps,
                metadata=md,
                attribution_card=attribution_card_rgba,
                overwrite=request.overwrite,
            )
        else:
            exporter = exporter_for_format(this_fmt)
            result = exporter.write(composition, path, metadata=md, overwrite=request.overwrite)
        written.append(result.path)
        if primary_result is None:
            primary_result = result
            out_path = result.path
            width_px, height_px = result.width, result.height
        if sidecar_enabled:
            _write_sidecar(
                result.path,
                md,
                scene,
                prepared.warnings if 'prepared' in locals() else (),
                request=request,
                preset_metadata=preset_obj.metadata,
            )

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    warnings = list(prepared.warnings) if 'prepared' in locals() else []

    md_for_result = dict(md)
    if len(written) > 1:
        md_for_result["WrittenPaths"] = ",".join(str(p) for p in written)

    # In-memory returns: when no `out` was given, the caller can take the
    # composed Figure (default) or the raw RenderScene (return_scene=True).
    # The composed Figure already carries attribution — it's not a way around
    # the CC BY 4.0 obligation, just a way to keep the render in memory.
    figure_out = fig if out_path is None else None
    scene_out = scene if (out_path is None and return_scene) else None
    # When returning a figure but no file, populate width/height from the figure.
    if figure_out is not None and width_px == 0:
        w_in, h_in = fig.get_size_inches()
        width_px = int(round(w_in * fig.dpi))
        height_px = int(round(h_in * fig.dpi))

    return RenderResult(
        path=str(out_path) if out_path else None,
        format=fmt,
        preset=request.preset,
        city=request.city,
        dataset_id=dataset.dataset_id,
        attribution=attribution_text,
        width=width_px,
        height=height_px,
        elapsed_ms=elapsed_ms,
        warnings=warnings,
        metadata=md_for_result,
        figure=figure_out,
        scene=scene_out,
    )


def list_presets() -> list[PresetMetadata]:
    return get_registry().list_metadata()


def _write_sidecar(
    out_path: Path,
    md: dict,
    scene,
    warnings: tuple,
    request: RenderRequest,
    preset_metadata,
) -> None:
    """Drop a `{out}.json` next to the artifact with the full reproducibility
    payload.

    Plan: "sidecar 包含 request、preset metadata、dataset id、warnings". The
    sidecar is meant to be self-contained: given just the sidecar a downstream
    tool should be able to identify how the artifact was produced and re-run
    the same render.
    """
    import json

    payload = {
        "Artifact": md,
        "Request": request.model_dump(mode="json"),
        "Preset": preset_metadata.model_dump(mode="json"),
        "Warnings": list(warnings),
        "Scene": {
            "bounds": list(scene.bounds),
            "n_layers": len(scene.layers),
            "semantic_metadata": dict(scene.semantic_metadata),
        },
    }
    sidecar_path = out_path.with_suffix(out_path.suffix + ".json")
    sidecar_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _render_attribution_card(composition):
    """Snapshot the composed figure as the mp4 attribution card."""
    import numpy as np
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = composition.figure
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    w, h = canvas.get_width_height()
    buf = np.frombuffer(canvas.buffer_rgba(), dtype=np.uint8).reshape(h, w, 4).copy()
    return buf
