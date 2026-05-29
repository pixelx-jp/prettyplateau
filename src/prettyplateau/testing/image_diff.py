"""Lightweight image comparison utilities for visual regression tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _open_rgb(p: Path | str) -> np.ndarray:
    img = Image.open(p).convert("RGB")
    return np.asarray(img, dtype=np.float32)


def rms_diff(a: Path | str, b: Path | str) -> float:
    """Per-pixel RMS difference normalised to [0, 1]. Robust to small antialias shifts."""
    A = _open_rgb(a)
    B = _open_rgb(b)
    if A.shape != B.shape:
        # Resize to the smaller image for a best-effort comparison.
        h = min(A.shape[0], B.shape[0])
        w = min(A.shape[1], B.shape[1])
        A = A[:h, :w]
        B = B[:h, :w]
    return float(np.sqrt(((A - B) ** 2).mean()) / 255.0)


def perceptual_hash(p: Path | str, size: int = 16) -> str:
    """A tiny dHash for high-level "did the layout change" comparisons."""
    img = Image.open(p).convert("L").resize((size + 1, size))
    arr = np.asarray(img, dtype=np.int16)
    diff = arr[:, 1:] > arr[:, :-1]
    bits = diff.flatten()
    n = bits.size
    out = []
    for i in range(0, n, 4):
        nib = 0
        for j in range(4):
            if i + j < n and bits[i + j]:
                nib |= 1 << (3 - j)
        out.append(format(nib, "x"))
    return "".join(out)
