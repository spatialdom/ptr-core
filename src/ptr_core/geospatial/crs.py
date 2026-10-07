"""Optional PROJ boundary for coordinate transformation."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ptr_core.geospatial._dependencies import require_dependency

if TYPE_CHECKING:
    from pyproj import Transformer


def create_transformer(source_crs: str, target_crs: str) -> Transformer:
    backend = require_dependency("pyproj", capability="transform_crs")
    return cast(
        "Transformer",
        backend.Transformer.from_crs(source_crs, target_crs, always_xy=True),
    )
