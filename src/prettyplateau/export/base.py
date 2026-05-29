from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from prettyplateau.compose.composer import ComposedArtifact


@dataclass
class ExportResult:
    path: Path
    width: int
    height: int
    metadata: dict[str, str] = field(default_factory=dict)


class Exporter(Protocol):
    format: str

    def write(
        self,
        artifact: ComposedArtifact,
        out_path: Path,
        *,
        metadata: dict[str, str],
        overwrite: bool = False,
    ) -> ExportResult:
        ...
