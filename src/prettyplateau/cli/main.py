"""prettyplateau CLI entry point."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from prettyplateau.api.render import list_presets, render
from prettyplateau.core.errors import PrettyPlateauError

app = typer.Typer(
    add_completion=False,
    help="Print-quality city visualizations from Project PLATEAU data.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
_console = Console()


@app.command("render")
def render_cmd(
    city: Annotated[str, typer.Option("--city", "-c", help="City slug or path to out_<city>/")],
    preset: Annotated[str, typer.Option("--preset", "-p", help="Preset id (see --list-presets)")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output file path")] ,
    theme: Annotated[str, typer.Option("--theme", help="Visual theme")] = "default",
    width: Annotated[int | None, typer.Option("--width", help="Output pixel width (default 3840)")] = None,
    height: Annotated[int | None, typer.Option("--height", help="Output pixel height (inferred from aspect if omitted)")] = None,
    dpi: Annotated[int, typer.Option("--dpi", help="Render DPI (300 = print)")] = 300,
    bbox: Annotated[str | None, typer.Option("--bbox", help="minLon,minLat,maxLon,maxLat")] = None,
    title: Annotated[str | None, typer.Option("--title", help="Title text drawn on the canvas")] = None,
    subtitle: Annotated[str | None, typer.Option("--subtitle", help="Subtitle text")] = None,
    data_root: Annotated[Path | None, typer.Option("--data-root", help="Directory containing out_<city>/")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite/--no-overwrite", help="Overwrite existing output file")] = False,
    option: Annotated[list[str] | None, typer.Option("--option", "-O", help="Preset-specific option as key=value (repeatable)")] = None,
    sidecar: Annotated[bool, typer.Option("--sidecar/--no-sidecar", help="Write {out}.json sidecar with full metadata")] = False,
    attribution_corner: Annotated[
        str,
        typer.Option(
            "--attribution-corner",
            help="Attribution placement corner: bottom-right (default), bottom-left, top-right, top-left",
        ),
    ] = "bottom-right",
) -> None:
    """Render a single PLATEAU visualization."""
    bbox_t = _parse_bbox(bbox) if bbox else None
    opts = _parse_options(option or [])
    # Brace expansion: `shibuya.{png,svg,pdf}` → render each format off the same
    # composed figure. Cheap for the user, and reuses the (expensive) data load.
    primary_out, extra_outs = _expand_brace_outputs(str(out))
    if extra_outs:
        opts["extra_outs"] = extra_outs
    if sidecar:
        opts["sidecar"] = True
    valid_corners = {"bottom-right", "bottom-left", "top-right", "top-left"}
    if attribution_corner not in valid_corners:
        _console.print(
            f"[red]error[/red]: --attribution-corner must be one of {sorted(valid_corners)}"
        )
        raise typer.Exit(code=2)
    opts["attribution_corner"] = attribution_corner
    # Plan: "CLI 解析参数为 `RenderRequest`. CLI 不自己拼接底层函数参数. CLI 调用
    # `prettyplateau.render(request)`." Build a typed RenderRequest here so the
    # CLI and Python API share a single validated execution contract — no
    # divergent kwarg-spreading paths.
    from prettyplateau.api.types import RenderRequest

    try:
        cli_request = RenderRequest(
            city=city,
            preset=preset,
            out=primary_out,
            theme=theme,
            bbox=bbox_t,
            width=width,
            height=height,
            dpi=dpi,
            title=title,
            subtitle=subtitle,
            overwrite=overwrite,
            options=opts,
        )
        result = render(
            request=cli_request,
            data_root=str(data_root) if data_root else None,
        )
    except PrettyPlateauError as exc:
        _console.print(f"[red]error[/red]: {exc}")
        raise typer.Exit(code=2) from exc

    _console.print(f"[green]wrote[/green] {result.path}  ({result.width}×{result.height}, {result.elapsed_ms} ms)")
    for w in result.warnings:
        _console.print(f"[yellow]warn[/yellow]: {w}")
    _console.print(f"[dim]{result.attribution}[/dim]")


@app.command("fetch")
def fetch_cmd(
    city: Annotated[str, typer.Argument(help="City slug (`shibuya`) or 5-digit JIS code (`13113`)")],
    dest_root: Annotated[
        Path | None,
        typer.Option("--data-root", help="Where to create out_<city>/ (default: current dir)"),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Re-download even if already present")] = False,
) -> None:
    """Download a prebuilt buildings.parquet for a city (no pipeline needed).

    Pulls the bundle from the public plateau-bridge index, verifies its
    sha256, and extracts it to out_<city>/ so `render` works immediately.
    """
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        TaskID,
        TextColumn,
        TransferSpeedColumn,
    )

    from prettyplateau.data.fetch import FetchError, fetch_city

    try:
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            console=_console,
            transient=True,
        ) as progress:
            task_id: TaskID | None = None

            def on_progress(done: int, total: int) -> None:
                nonlocal task_id
                if task_id is None:
                    task_id = progress.add_task(f"fetch {city}", total=total)
                progress.update(task_id, completed=done)

            out_dir, entry = fetch_city(
                city, dest_root=dest_root, force=force, on_progress=on_progress
            )
    except FetchError as exc:
        _console.print(f"[red]error[/red]: {exc}")
        raise typer.Exit(code=2) from exc

    _console.print(
        f"[green]ready[/green] {out_dir}  "
        f"({entry.city_name} {entry.dataset_year}, {entry.n_buildings:,} buildings)"
    )
    _console.print(
        f"[dim]next:[/dim] prettyplateau render --city {entry.slug} --preset use_mosaic "
        f"--out {entry.slug}.png"
        + (f" --data-root {dest_root}" if dest_root else "")
    )


@app.command("list-presets")
def list_presets_cmd() -> None:
    """List registered presets."""
    table = Table(title="prettyplateau presets")
    table.add_column("id", style="bold")
    table.add_column("modes")
    table.add_column("required fields")
    table.add_column("description")
    for meta in list_presets():
        table.add_row(
            meta.id,
            ",".join(meta.modes),
            ",".join(meta.required_fields) or "—",
            meta.description,
        )
    _console.print(table)


@app.command("create-preset")
def create_preset_cmd(
    preset_id: Annotated[str, typer.Argument(help="Preset id (snake or kebab case)")],
    dest: Annotated[Path, typer.Option("--dest", help="Destination directory")] = Path("."),
    name: Annotated[str | None, typer.Option("--name", help="Display name (default: title-cased id)")] = None,
) -> None:
    """Emit a working community preset skeleton — runnable in five minutes."""
    from prettyplateau.cli.scaffold import scaffold

    try:
        paths = scaffold(preset_id, dest, name)
    except ValueError as exc:
        _console.print(f"[red]error[/red]: {exc}")
        raise typer.Exit(code=2) from exc
    _console.print(f"[green]created[/green] {paths.preset_file.parent.parent.parent}")
    _console.print(f"  preset:    {paths.preset_file}")
    _console.print(f"  palette:   {paths.palette_file}")
    _console.print(f"  test:      {paths.test_file}")
    _console.print(f"  pyproject: {paths.pyproject_file}")
    _console.print("\nNext: cd into the new dir, `pip install -e .[dev]`, and `pytest`.")


@app.command("themes")
def themes_cmd() -> None:
    """List available themes."""
    from prettyplateau.style.theme import list_themes

    table = Table(title="prettyplateau themes")
    table.add_column("id", style="bold")
    table.add_column("name")
    table.add_column("background")
    table.add_column("accent")
    for theme in list_themes():
        table.add_row(theme.id, theme.name, theme.background, theme.accent)
    _console.print(table)


_BRACE_RE = re.compile(r"\{([^{}]+)\}")


def _expand_brace_outputs(value: str) -> tuple[str, list[str]]:
    """Expand a single `name.{ext1,ext2,ext3}` pattern into a primary path
    and a list of additional paths. Only one brace group is supported because
    that's all anyone would actually use; multiplying brace groups is a
    foot-gun, not a feature.
    """
    m = _BRACE_RE.search(value)
    if not m:
        return value, []
    exts = [e.strip() for e in m.group(1).split(",") if e.strip()]
    if not exts:
        return value, []
    expanded = [_BRACE_RE.sub(ext, value, count=1) for ext in exts]
    return expanded[0], expanded[1:]


def _parse_options(pairs: list[str]) -> dict[str, object]:
    """Parse --option k=v / k=int / k=float pairs."""
    out: dict[str, object] = {}
    for p in pairs:
        if "=" not in p:
            _console.print(f"[red]error[/red]: --option must be key=value, got {p!r}")
            sys.exit(2)
        k, v = p.split("=", 1)
        k = k.strip()
        v = v.strip()
        try:
            out[k] = int(v)
            continue
        except ValueError:
            pass
        try:
            out[k] = float(v)
            continue
        except ValueError:
            pass
        if v.lower() in ("true", "false"):
            out[k] = v.lower() == "true"
        else:
            out[k] = v
    return out


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 4:
        _console.print("[red]error[/red]: --bbox must be minLon,minLat,maxLon,maxLat")
        sys.exit(2)
    minx, miny, maxx, maxy = (float(p) for p in parts)
    return (minx, miny, maxx, maxy)


if __name__ == "__main__":
    app()
