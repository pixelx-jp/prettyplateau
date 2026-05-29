"""Renderer protocol — the abstraction that lets us swap backends.

The plan calls out `MatplotlibRenderer` as the default and reserves
`CairoRenderer` / `SkiaRenderer` as future performance plug-ins. They all
implement the same `Renderer` contract: take a `RenderScene` + `Theme` +
`RenderOptions`, return a matplotlib-compatible `Figure`. Backends that
can't natively produce a `Figure` are expected to wrap their output.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from matplotlib.figure import Figure

from prettyplateau.presets.scene import RenderScene
from prettyplateau.renderers.matplotlib_renderer import (
    PersistentRender,
    RenderOptions,
)
from prettyplateau.style.theme import Theme


@runtime_checkable
class Renderer(Protocol):
    """Stable surface that every backend must expose.

    Methods kept tiny so third-party renderers don't have to implement an
    entire matplotlib clone. Optional methods (`render_persistent`,
    `update_layer_fills`) light up animation performance when supported;
    fall-back is `render()` per frame.
    """

    def render(
        self,
        scene: RenderScene,
        theme: Theme,
        options: RenderOptions,
    ) -> Figure:
        """Render a scene to a matplotlib Figure (or compatible wrapper)."""
        ...

    def render_persistent(
        self,
        scene: RenderScene,
        theme: Theme,
        options: RenderOptions,
    ) -> PersistentRender:
        """Optional: return a handle whose fills can be mutated for animations."""
        ...
