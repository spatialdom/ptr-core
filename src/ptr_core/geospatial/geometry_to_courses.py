"""Derive PTR-style courses from compatible simple polygon geometry."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import atan2, degrees, hypot, isclose
from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from shapely.geometry import Polygon

from ptr_core.bearings import parse_bearing
from ptr_core.geospatial._dependencies import require_dependency
from ptr_core.models import PTR_VERSION, Course

Coordinate = tuple[float, float]
GeometryInput: TypeAlias = "Polygon | Sequence[Coordinate]"


class GeometryToCoursesError(ValueError):
    """Raised when geometry cannot be converted into PTR-style courses."""


@dataclass(frozen=True, slots=True)
class PTRCourseCandidate:
    """Computationally derived PTR course sequence.

    This is a candidate representation derived from geometry. It is not
    documentary truth and does not invent tie points, declared area, or source
    provenance.
    """

    lines: tuple[Course, ...]
    coordinate_frame: str
    winding: str
    distance_decimals: int
    bearing_precision: str = "nearest_second"

    def to_mapping(self) -> dict[str, Any]:
        return {
            "ptr_version": PTR_VERSION,
            "lines": [line.to_json_value() for line in self.lines],
        }

    def to_metadata(self) -> dict[str, str | int]:
        return {
            "coordinate_frame": self.coordinate_frame,
            "winding": self.winding,
            "distance_decimals": self.distance_decimals,
            "bearing_precision": self.bearing_precision,
        }


def derive_courses_from_polygon(
    geometry: GeometryInput,
    *,
    coordinate_frame: str,
    distance_decimals: int = 12,
) -> PTRCourseCandidate:
    """Derive ordered PTR bearing-distance courses from a simple polygon.

    Output courses are rotated to a deterministic start point and ordered
    clockwise to match the PTR v0.1 writing convention. Distances are rounded to
    ``distance_decimals`` decimal places. Bearings are rounded to the nearest
    whole second and serialized in canonical PTR syntax.
    """

    if not coordinate_frame or not coordinate_frame.strip():
        raise GeometryToCoursesError("coordinate_frame must identify a metric frame.")
    if distance_decimals < 0:
        raise GeometryToCoursesError("distance_decimals must be non-negative.")

    polygon = _polygon_from_input(geometry)
    _validate_supported_polygon(polygon)
    ring = _open_ring(tuple((float(x), float(y)) for x, y in polygon.exterior.coords))
    ring = _clockwise_ring(ring)
    ring = _rotate_to_deterministic_start(ring)
    courses = tuple(
        _course_from_segment(start, end, distance_decimals=distance_decimals)
        for start, end in zip(ring, (*ring[1:], ring[0]), strict=True)
    )
    return PTRCourseCandidate(
        lines=courses,
        coordinate_frame=coordinate_frame,
        winding="clockwise",
        distance_decimals=distance_decimals,
    )


def _polygon_from_input(geometry: GeometryInput) -> Polygon:
    module = require_dependency(
        "shapely.geometry", capability="derive_courses_from_polygon"
    )
    base = require_dependency(
        "shapely.geometry.base", capability="derive_courses_from_polygon"
    )
    if isinstance(geometry, module.Polygon):
        return geometry
    if isinstance(geometry, base.BaseGeometry):
        raise GeometryToCoursesError("Only simple Polygon geometry is supported.")
    if len(geometry) < 3:
        raise GeometryToCoursesError("A polygon ring must contain at least 3 points.")
    return module.Polygon(geometry)


def _validate_supported_polygon(polygon: Polygon) -> None:
    if polygon.is_empty:
        raise GeometryToCoursesError("Polygon must not be empty.")
    if len(polygon.interiors) > 0:
        raise GeometryToCoursesError("Polygons with holes are not supported.")
    if not polygon.is_valid or not polygon.exterior.is_simple:
        raise GeometryToCoursesError("Polygon must be simple and valid.")
    if polygon.area <= 0:
        raise GeometryToCoursesError("Polygon area must be greater than zero.")


def _open_ring(ring: tuple[Coordinate, ...]) -> tuple[Coordinate, ...]:
    if len(ring) < 4:
        raise GeometryToCoursesError("Polygon exterior must contain a closed ring.")
    if _same_coordinate(ring[0], ring[-1]):
        return ring[:-1]
    return ring


def _clockwise_ring(ring: tuple[Coordinate, ...]) -> tuple[Coordinate, ...]:
    if _signed_area(ring) > 0:
        return (ring[0], *reversed(ring[1:]))
    return ring


def _rotate_to_deterministic_start(
    ring: tuple[Coordinate, ...],
) -> tuple[Coordinate, ...]:
    start_index = min(
        range(len(ring)), key=lambda index: (ring[index][0], ring[index][1])
    )
    return (*ring[start_index:], *ring[:start_index])


def _course_from_segment(
    start: Coordinate, end: Coordinate, *, distance_decimals: int
) -> Course:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    distance = round(hypot(dx, dy), distance_decimals)
    if distance <= 0:
        raise GeometryToCoursesError("Polygon contains a zero-length segment.")
    return Course(
        bearing=parse_bearing(_bearing_from_delta(dx, dy), normalize=False),
        distance=distance,
    )


def _bearing_from_delta(dx: float, dy: float) -> str:
    if isclose(dx, 0.0, abs_tol=1e-12) and dy > 0:
        return "N"
    if isclose(dy, 0.0, abs_tol=1e-12) and dx > 0:
        return "E"
    if isclose(dx, 0.0, abs_tol=1e-12) and dy < 0:
        return "S"
    if isclose(dy, 0.0, abs_tol=1e-12) and dx < 0:
        return "W"

    azimuth = (degrees(atan2(dx, dy)) + 360) % 360
    if isclose(azimuth, 0.0, abs_tol=1e-12) or isclose(azimuth, 360.0, abs_tol=1e-12):
        return "N"
    if isclose(azimuth, 90.0, abs_tol=1e-12):
        return "E"
    if isclose(azimuth, 180.0, abs_tol=1e-12):
        return "S"
    if isclose(azimuth, 270.0, abs_tol=1e-12):
        return "W"

    if 0 < azimuth < 90:
        return _quadrant_bearing("N", azimuth, "E")
    if 90 < azimuth < 180:
        return _quadrant_bearing("S", 180 - azimuth, "E")
    if 180 < azimuth < 270:
        return _quadrant_bearing("S", azimuth - 180, "W")
    return _quadrant_bearing("N", 360 - azimuth, "W")


def _quadrant_bearing(ns: str, offset_degrees: float, ew: str) -> str:
    total_seconds = round(offset_degrees * 3600)
    if total_seconds <= 0:
        return ns
    if total_seconds >= 90 * 3600:
        return ew
    degree, remainder = divmod(total_seconds, 3600)
    minute, second = divmod(remainder, 60)
    value = f"{ns}{degree}-{minute:02d}"
    if second:
        value += f"-{second:02d}"
    return f"{value}{ew}"


def _signed_area(ring: tuple[Coordinate, ...]) -> float:
    total = 0.0
    for index, point in enumerate(ring):
        next_point = ring[(index + 1) % len(ring)]
        total += point[0] * next_point[1] - next_point[0] * point[1]
    return total / 2


def _same_coordinate(left: Coordinate, right: Coordinate) -> bool:
    return isclose(left[0], right[0], abs_tol=1e-12) and isclose(
        left[1], right[1], abs_tol=1e-12
    )
