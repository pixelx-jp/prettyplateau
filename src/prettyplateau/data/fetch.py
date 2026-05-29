"""Fetch a prebuilt ``buildings.parquet`` bundle so the CLI works standalone.

prettyplateau does not redistribute PLATEAU data — it renders the
``buildings.parquet`` that `plateau-bridge` produces. To save casual users
from cloning the pipeline and processing gigabytes of CityGML, the bridge
publishes prebuilt per-city bundles and a small JSON index. This module reads
that public index, downloads the bundle for a city, verifies its sha256, and
extracts it into ``out_<slug>/`` — exactly where ``discover_city`` looks.

The bundle is a ``.tar.zst`` (one per city/year); we only need
``buildings.parquet`` + ``manifest.json`` out of it, but extract the lot since
it is small once the heavy 3D Tiles are excluded (they are, upstream).
"""

from __future__ import annotations

import hashlib
import json
import tarfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from prettyplateau._core_lite.loader import CITY_ALIASES

# Same index the plateau-bridge pipeline and plateau-creative-mcp read.
DEFAULT_INDEX_URL = (
    "https://raw.githubusercontent.com/pixelx-jp/plateau-bridge/main/distribution/index.json"
)

# Local cache so a second `fetch` of the same city is instant and offline-safe.
CACHE_ROOT = Path.home() / ".cache" / "prettyplateau" / "bundles"

_CHUNK = 1 << 16


class FetchError(RuntimeError):
    """Anything that goes wrong resolving, downloading, or extracting a bundle."""


@dataclass(frozen=True)
class BundleEntry:
    city_code: str
    city_name: str
    dataset_year: int
    bundle_url: str
    sha256: str
    bytes: int
    n_buildings: int
    slug: str


def _slugify_city_name(name: str) -> str:
    """``"Chiyoda-ku"`` → ``"chiyoda"``, ``"Osaka-shi"`` → ``"osaka"``.

    The index labels cities by their romanised admin name; we reduce that to the
    same bare slug `discover_city`/`CITY_ALIASES` use as the ``out_<slug>`` key.
    """
    base = name.split("-", 1)[0] if "-" in name else name
    return base.strip().lower()


def _http_get_bytes(url: str, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "prettyplateau-fetch"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https index)
        return resp.read()


def load_index(index_url: str = DEFAULT_INDEX_URL) -> list[BundleEntry]:
    """Read the public cache index into typed entries (newest year first)."""
    try:
        if index_url.startswith("file://"):
            raw = Path(index_url[len("file://") :]).read_text(encoding="utf-8")
        else:
            raw = _http_get_bytes(index_url).decode("utf-8")
        doc = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 — surface any network/parse failure uniformly
        raise FetchError(f"could not read bundle index {index_url}: {exc}") from exc
    entries = [
        BundleEntry(
            city_code=c["city_code"],
            city_name=c["city_name"],
            dataset_year=int(c["dataset_year"]),
            bundle_url=c["bundle_url"],
            sha256=c["sha256"],
            bytes=int(c["bytes"]),
            n_buildings=int(c.get("n_buildings", 0)),
            slug=_slugify_city_name(c["city_name"]),
        )
        for c in doc.get("cities", [])
    ]
    entries.sort(key=lambda e: e.dataset_year, reverse=True)
    return entries


def resolve_entry(city: str, entries: list[BundleEntry]) -> BundleEntry:
    """Resolve a slug (``shibuya``) or 5-digit JIS code (``13113``) to one entry."""
    key = city.strip().lower()
    # Exact JIS code wins (most specific).
    for e in entries:
        if e.city_code == key:
            return e
    # Slug, possibly via the same alias table the loader uses.
    alias_slugs = {key, *(_slugify_city_name(a) for a in CITY_ALIASES.get(key, ()))}
    for e in entries:
        if e.slug in alias_slugs:
            return e
    available = ", ".join(sorted({e.slug for e in entries}))
    raise FetchError(f"city {city!r} not in the prebuilt bundle index. Available: {available}")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(entry: BundleEntry, dest: Path, on_progress: Callable[[int, int], None] | None) -> None:
    req = urllib.request.Request(entry.bundle_url, headers={"User-Agent": "prettyplateau-fetch"})
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310 (https release asset)
        total = int(resp.headers.get("content-length") or entry.bytes)
        done = 0
        with dest.open("wb") as f:
            while True:
                chunk = resp.read(_CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if on_progress:
                    on_progress(done, total)


def _extract_zst_tar(bundle_path: Path, dest: Path) -> None:
    try:
        import zstandard  # noqa: PLC0415 — optional-at-runtime, imported lazily
    except ImportError as exc:  # pragma: no cover - dependency declared in pyproject
        raise FetchError(
            "the 'zstandard' package is required to extract bundles; "
            "reinstall prettyplateau (pip install --upgrade prettyplateau)"
        ) from exc

    dest.mkdir(parents=True, exist_ok=True)
    dctx = zstandard.ZstdDecompressor()
    with bundle_path.open("rb") as fh, dctx.stream_reader(fh) as reader:
        with tarfile.open(fileobj=reader, mode="r|") as tar:
            try:
                tar.extractall(dest, filter="data")  # type: ignore[call-arg]
            except TypeError:  # Python < 3.12 has no `filter` kwarg
                tar.extractall(dest)  # noqa: S202 — our own trusted bundles


def fetch_city(
    city: str,
    *,
    dest_root: Path | None = None,
    index_url: str = DEFAULT_INDEX_URL,
    force: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[Path, BundleEntry]:
    """Download + verify + extract the bundle for ``city`` into ``out_<slug>/``.

    Returns ``(out_dir, entry)``. Raises :class:`FetchError` on any failure.
    """
    entries = load_index(index_url)
    entry = resolve_entry(city, entries)

    dest_root = Path(dest_root) if dest_root else Path.cwd()
    out_dir = dest_root / f"out_{entry.slug}"
    if (out_dir / "buildings.parquet").is_file() and not force:
        return out_dir, entry

    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    bundle_path = CACHE_ROOT / f"plateau-{entry.city_code}-{entry.dataset_year}-{entry.sha256[:8]}.tar.zst"

    if not bundle_path.exists() or _sha256_file(bundle_path) != entry.sha256:
        tmp = bundle_path.with_suffix(".tar.zst.part")
        _download(entry, tmp, on_progress)
        got = _sha256_file(tmp)
        if got != entry.sha256:
            tmp.unlink(missing_ok=True)
            raise FetchError(
                f"sha256 mismatch for {bundle_path.name}: expected {entry.sha256}, got {got}"
            )
        tmp.replace(bundle_path)

    _extract_zst_tar(bundle_path, out_dir)
    if not (out_dir / "buildings.parquet").is_file():
        raise FetchError(f"bundle extracted but {out_dir / 'buildings.parquet'} is missing")
    return out_dir, entry
