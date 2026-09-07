"""GeoJSON and WKT exports for derived PTR geometry."""

from __future__ import annotations

from typing import Any

from ptr_core.geometry import DerivedParcel, Point, polygon_signed_area
from ptr_core.georeferencing import GeoreferencedParcel


def to_geojson(parcel: DerivedParcel | GeoreferencedParcel) -> dict[str, Any]:
    """Export derived parcel geometry as a GeoJSON Feature."""

    ring = _export_ring(parcel)
    properties = _properties(parcel)
    geometry: dict[str, Any] = {
        "type": "Polygon",
        "coordinates": [[[_clean(point.x), _clean(point.y)] for point in ring]],
    }
    return {"type": "Feature", "properties": properties, "geometry": geometry}


def to_wkt(parcel: DerivedParcel | GeoreferencedParcel) -> str:
    """Export derived parcel geometry as WKT Polygon text."""

    coords = ", ".join(
        f"{_format(point.x)} {_format(point.y)}" for point in _export_ring(parcel)
    )
    return f"POLYGON (({coords}))"


def _export_ring(parcel: DerivedParcel | GeoreferencedParcel) -> tuple[Point, ...]:
    points = list(parcel.vertices)
    if not _same_point(points[-1], parcel.final_endpoint):
        points.append(parcel.final_endpoint)
    if not _same_point(points[-1], points[0]):
        points.append(points[0])
    if polygon_signed_area(tuple(points[:-1])) < 0:
        start = points[0]
        points = [start, *reversed(points[1:-1]), start]
    return tuple(points)


def _properties(parcel: DerivedParcel | GeoreferencedParcel) -> dict[str, Any]:
    source = parcel.local if isinstance(parcel, GeoreferencedParcel) else parcel
    properties: dict[str, Any] = {
        "ptr_version": source.record.ptr_version,
        "derived_from_ptr": True,
        "georeferenced": isinstance(parcel, GeoreferencedParcel),
    }
    if source.record.name is not None:
        properties["name"] = source.record.name
    if source.record.record_id is not None:
        properties["record_id"] = source.record.record_id
    if isinstance(parcel, GeoreferencedParcel):
        properties["crs"] = parcel.crs
    return properties


def _same_point(left: Point, right: Point, tolerance: float = 1e-9) -> bool:
    return abs(left.x - right.x) <= tolerance and abs(left.y - right.y) <= tolerance


def _clean(value: float) -> float:
    if abs(value) <= 1e-12:
        return 0.0
    return value


def _format(value: float) -> str:
    return f"{_clean(value):.12g}"
