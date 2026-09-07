"""Derived local geometry for PTR records.

The coordinate convention is local only: ``x`` is Easting in metres and ``y``
is Northing in metres. It does not imply a real-world CRS or tie-point location.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, hypot, radians, sin

from ptr_core.models import Course, PTRRecord
from ptr_core.validation import Diagnostic, Severity

DEFAULT_CLOSURE_TOLERANCE_METRES = 1e-9
DEFAULT_AREA_TOLERANCE_SQ_METRES = 1e-9


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Vector:
    dx: float
    dy: float

    @property
    def length(self) -> float:
        return hypot(self.dx, self.dy)


@dataclass(frozen=True, slots=True)
class Closure:
    east: float
    north: float
    linear: float
    tolerance: float

    @property
    def is_closed(self) -> bool:
        return self.linear <= self.tolerance


@dataclass(frozen=True, slots=True)
class AreaComparison:
    declared_area: float
    computed_area: float
    absolute_difference: float
    relative_difference: float


@dataclass(frozen=True, slots=True)
class ParcelMetrics:
    perimeter: float
    signed_area: float
    area: float
    closure: Closure
    declared_area_comparison: AreaComparison | None


@dataclass(frozen=True, slots=True)
class DerivedParcel:
    """Computational parcel derived from a documentary PTR record."""

    record: PTRRecord
    origin: Point
    vertices: tuple[Point, ...]
    final_endpoint: Point
    course_vectors: tuple[Vector, ...]
    metrics: ParcelMetrics
    qa_findings: tuple[Diagnostic, ...]


def course_to_vector(course: Course) -> Vector:
    """Convert one bearing-distance course into local Cartesian deltas."""

    bearing = course.bearing.canonical
    distance = course.distance
    if bearing == "N":
        return Vector(0.0, distance)
    if bearing == "E":
        return Vector(distance, 0.0)
    if bearing == "S":
        return Vector(0.0, -distance)
    if bearing == "W":
        return Vector(-distance, 0.0)

    azimuth = radians(course.bearing.azimuth_degrees)
    return Vector(sin(azimuth) * distance, cos(azimuth) * distance)


def reconstruct(
    record: PTRRecord,
    *,
    closure_tolerance: float = DEFAULT_CLOSURE_TOLERANCE_METRES,
    area_tolerance: float = DEFAULT_AREA_TOLERANCE_SQ_METRES,
) -> DerivedParcel:
    """Reconstruct a PTR boundary traverse in a local Cartesian frame."""

    origin = Point(0.0, 0.0)
    current = origin
    vertices: list[Point] = [origin]
    vectors: list[Vector] = []

    for index, course in enumerate(record.lines):
        vector = course_to_vector(course)
        vectors.append(vector)
        current = Point(current.x + vector.dx, current.y + vector.dy)
        if index < len(record.lines) - 1:
            vertices.append(current)

    final_endpoint = current
    closure = Closure(
        east=final_endpoint.x - origin.x,
        north=final_endpoint.y - origin.y,
        linear=hypot(final_endpoint.x - origin.x, final_endpoint.y - origin.y),
        tolerance=closure_tolerance,
    )
    signed_area = polygon_signed_area((*vertices, final_endpoint))
    area = abs(signed_area)
    comparison = _compare_declared_area(record.declared_area, area)
    metrics = ParcelMetrics(
        perimeter=sum(course.distance for course in record.lines),
        signed_area=signed_area,
        area=area,
        closure=closure,
        declared_area_comparison=comparison,
    )
    findings = _qa_findings(
        vertices=tuple(vertices),
        final_endpoint=final_endpoint,
        metrics=metrics,
        closure_tolerance=closure_tolerance,
        area_tolerance=area_tolerance,
    )

    return DerivedParcel(
        record=record,
        origin=origin,
        vertices=tuple(vertices),
        final_endpoint=final_endpoint,
        course_vectors=tuple(vectors),
        metrics=metrics,
        qa_findings=findings,
    )


def compute_metrics(parcel: DerivedParcel) -> ParcelMetrics:
    return parcel.metrics


def polygon_signed_area(points: tuple[Point, ...]) -> float:
    """Return shoelace signed area, closing the supplied path to the first point."""

    if len(points) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        total += point.x * next_point.y - next_point.x * point.y
    return total / 2


def _compare_declared_area(
    declared_area: float | None, computed_area: float
) -> AreaComparison | None:
    if declared_area is None:
        return None
    absolute = abs(computed_area - declared_area)
    return AreaComparison(
        declared_area=declared_area,
        computed_area=computed_area,
        absolute_difference=absolute,
        relative_difference=absolute / declared_area,
    )


def _qa_findings(
    *,
    vertices: tuple[Point, ...],
    final_endpoint: Point,
    metrics: ParcelMetrics,
    closure_tolerance: float,
    area_tolerance: float,
) -> tuple[Diagnostic, ...]:
    findings: list[Diagnostic] = []
    if metrics.closure.linear > closure_tolerance:
        findings.append(
            Diagnostic(
                "geometric_qa",
                "misclosure",
                "Computed final endpoint does not return to Point 1.",
                "$.lines",
                Severity.WARNING,
            )
        )
    if metrics.signed_area > area_tolerance:
        findings.append(
            Diagnostic(
                "geometric_qa",
                "counterclockwise_orientation",
                "Boundary courses reconstruct counterclockwise; PTR v0.1 "
                "prefers clockwise order.",
                "$.lines",
                Severity.WARNING,
            )
        )
    if metrics.area <= area_tolerance:
        findings.append(
            Diagnostic(
                "geometric_qa",
                "degenerate_area",
                "Derived polygon area is zero or near zero.",
                "$.lines",
                Severity.WARNING,
            )
        )
    path = (*vertices, final_endpoint)
    has_duplicate_vertices = _has_duplicate_vertices(path, closure_tolerance)
    if has_duplicate_vertices:
        findings.append(
            Diagnostic(
                "geometric_qa",
                "duplicate_vertex",
                "Derived traverse contains duplicate nonconsecutive vertices.",
                "$.lines",
                Severity.WARNING,
            )
        )
    if has_duplicate_vertices or _has_self_intersection(path, closure_tolerance):
        findings.append(
            Diagnostic(
                "geometric_qa",
                "self_intersection",
                "Derived traverse contains crossing boundary segments.",
                "$.lines",
                Severity.WARNING,
            )
        )
    comparison = metrics.declared_area_comparison
    if comparison is not None and comparison.absolute_difference > area_tolerance:
        findings.append(
            Diagnostic(
                "geometric_qa",
                "declared_area_difference",
                "Computed area differs from declared_area.",
                "$.declared_area",
                Severity.WARNING,
            )
        )
    return tuple(findings)


def _has_duplicate_vertices(points: tuple[Point, ...], tolerance: float) -> bool:
    last_index = len(points) - 1
    for left_index, left in enumerate(points):
        for right_index in range(left_index + 1, len(points)):
            if left_index == 0 and right_index == last_index:
                continue
            right = points[right_index]
            if hypot(left.x - right.x, left.y - right.y) <= tolerance:
                return True
    return False


def _has_self_intersection(points: tuple[Point, ...], tolerance: float) -> bool:
    segments = tuple(zip(points, points[1:], strict=False))
    for left_index, left in enumerate(segments):
        for right_index in range(left_index + 1, len(segments)):
            if abs(left_index - right_index) <= 1:
                continue
            right = segments[right_index]
            if _segments_share_endpoint(left, right, tolerance):
                continue
            if _segments_intersect(left[0], left[1], right[0], right[1], tolerance):
                return True
    return False


def _segments_share_endpoint(
    left: tuple[Point, Point], right: tuple[Point, Point], tolerance: float
) -> bool:
    return any(
        hypot(left_point.x - right_point.x, left_point.y - right_point.y) <= tolerance
        for left_point in left
        for right_point in right
    )


def _segments_intersect(
    a: Point, b: Point, c: Point, d: Point, tolerance: float
) -> bool:
    o1 = _orientation(a, b, c, tolerance)
    o2 = _orientation(a, b, d, tolerance)
    o3 = _orientation(c, d, a, tolerance)
    o4 = _orientation(c, d, b, tolerance)

    if o1 == 0 and _on_segment(a, c, b, tolerance):
        return True
    if o2 == 0 and _on_segment(a, d, b, tolerance):
        return True
    if o3 == 0 and _on_segment(c, a, d, tolerance):
        return True
    if o4 == 0 and _on_segment(c, b, d, tolerance):
        return True
    return o1 != o2 and o3 != o4


def _orientation(a: Point, b: Point, c: Point, tolerance: float) -> int:
    value = (b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y)
    if abs(value) <= tolerance:
        return 0
    return 1 if value > 0 else 2


def _on_segment(a: Point, b: Point, c: Point, tolerance: float) -> bool:
    return (
        min(a.x, c.x) - tolerance <= b.x <= max(a.x, c.x) + tolerance
        and min(a.y, c.y) - tolerance <= b.y <= max(a.y, c.y) + tolerance
    )
