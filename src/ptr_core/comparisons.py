"""Parcel-to-parcel comparison primitives."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any

from ptr_core.geometry import DerivedParcel, Point, Vector
from ptr_core.georeferencing import GeoreferencedParcel
from ptr_core.models import Course, PTRRecord

ComparableParcel = DerivedParcel | GeoreferencedParcel


@dataclass(frozen=True, slots=True)
class CourseComparison:
    index: int
    left_bearing: str | None
    right_bearing: str | None
    bearing_equal: bool
    left_distance: float | None
    right_distance: float | None
    distance_difference: float | None
    distance_equal: bool

    @property
    def equal(self) -> bool:
        return self.bearing_equal and self.distance_equal


@dataclass(frozen=True, slots=True)
class BoundingBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def area(self) -> float:
        return max(0.0, self.max_x - self.min_x) * max(0.0, self.max_y - self.min_y)


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """Structured comparison result.

    The result reports evidence and metrics only. It does not declare legal
    identity, ownership, cadastral correctness, or authoritative sameness.
    """

    compatible_frame: bool
    frame_reason: str
    crs: str | None
    documentary_equal: bool
    line_count_equal: bool
    course_comparisons: tuple[CourseComparison, ...]
    geometry_equal: bool | None
    geometry_equivalent_by_translation: bool | None
    area_difference: float
    perimeter_difference: float
    centroid_translation: Vector | None
    centroid_distance: float | None
    max_vertex_distance: float | None
    hausdorff_distance: float | None
    bounding_box_overlap_area: float | None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "compatible_frame": self.compatible_frame,
            "frame_reason": self.frame_reason,
            "crs": self.crs,
            "documentary_equal": self.documentary_equal,
            "line_count_equal": self.line_count_equal,
            "course_comparisons": [
                {
                    "index": comparison.index,
                    "left_bearing": comparison.left_bearing,
                    "right_bearing": comparison.right_bearing,
                    "bearing_equal": comparison.bearing_equal,
                    "left_distance": comparison.left_distance,
                    "right_distance": comparison.right_distance,
                    "distance_difference": comparison.distance_difference,
                    "distance_equal": comparison.distance_equal,
                    "equal": comparison.equal,
                }
                for comparison in self.course_comparisons
            ],
            "geometry_equal": self.geometry_equal,
            "geometry_equivalent_by_translation": (
                self.geometry_equivalent_by_translation
            ),
            "area_difference": self.area_difference,
            "perimeter_difference": self.perimeter_difference,
            "centroid_translation": None
            if self.centroid_translation is None
            else {
                "dx": self.centroid_translation.dx,
                "dy": self.centroid_translation.dy,
            },
            "centroid_distance": self.centroid_distance,
            "max_vertex_distance": self.max_vertex_distance,
            "hausdorff_distance": self.hausdorff_distance,
            "bounding_box_overlap_area": self.bounding_box_overlap_area,
        }


def compare_parcels(
    left: ComparableParcel,
    right: ComparableParcel,
    *,
    distance_tolerance: float,
    area_tolerance: float,
) -> ComparisonResult:
    """Compare two derived parcels with explicit tolerances."""

    frame = _frame_compatibility(left, right)
    left_local = _local(left)
    right_local = _local(right)
    course_comparisons = _compare_courses(
        left_local.record.lines,
        right_local.record.lines,
        distance_tolerance=distance_tolerance,
    )
    left_points = _points(left)
    right_points = _points(right)
    translated_right = _translate_points(
        right_points,
        _centroid(left_points).x - _centroid(right_points).x,
        _centroid(left_points).y - _centroid(right_points).y,
    )
    shape_equivalent = _same_vertices(
        left_points, translated_right, distance_tolerance=distance_tolerance
    )

    geometry_equal = None
    centroid_translation = None
    centroid_distance = None
    max_vertex_distance = None
    hausdorff = None
    overlap = None
    if frame.compatible:
        geometry_equal = _same_vertices(
            left_points, right_points, distance_tolerance=distance_tolerance
        )
        left_centroid = _centroid(left_points)
        right_centroid = _centroid(right_points)
        centroid_translation = Vector(
            right_centroid.x - left_centroid.x,
            right_centroid.y - left_centroid.y,
        )
        centroid_distance = centroid_translation.length
        max_vertex_distance = _max_vertex_distance(left_points, right_points)
        hausdorff = _hausdorff_distance(left_points, right_points)
        overlap = _bbox_overlap(_bounding_box(left_points), _bounding_box(right_points))

    return ComparisonResult(
        compatible_frame=frame.compatible,
        frame_reason=frame.reason,
        crs=frame.crs,
        documentary_equal=_documentary_equal(left_local.record, right_local.record),
        line_count_equal=len(left_local.record.lines) == len(right_local.record.lines),
        course_comparisons=course_comparisons,
        geometry_equal=geometry_equal,
        geometry_equivalent_by_translation=shape_equivalent,
        area_difference=abs(left_local.metrics.area - right_local.metrics.area),
        perimeter_difference=abs(
            left_local.metrics.perimeter - right_local.metrics.perimeter
        ),
        centroid_translation=centroid_translation,
        centroid_distance=centroid_distance,
        max_vertex_distance=max_vertex_distance,
        hausdorff_distance=hausdorff,
        bounding_box_overlap_area=overlap,
    )


@dataclass(frozen=True, slots=True)
class _FrameCompatibility:
    compatible: bool
    reason: str
    crs: str | None


def _frame_compatibility(
    left: ComparableParcel, right: ComparableParcel
) -> _FrameCompatibility:
    if isinstance(left, GeoreferencedParcel) and isinstance(
        right, GeoreferencedParcel
    ):
        left_crs = left.crs
        right_crs = right.crs
        if left_crs == right_crs:
            return _FrameCompatibility(True, "same_crs", left_crs)
        return _FrameCompatibility(False, "different_crs", None)
    if not isinstance(left, GeoreferencedParcel) and not isinstance(
        right, GeoreferencedParcel
    ):
        return _FrameCompatibility(True, "local_unreferenced", None)
    return _FrameCompatibility(False, "mixed_local_and_georeferenced", None)


def _local(parcel: ComparableParcel) -> DerivedParcel:
    return parcel.local if isinstance(parcel, GeoreferencedParcel) else parcel


def _points(parcel: ComparableParcel) -> tuple[Point, ...]:
    return (*parcel.vertices, parcel.final_endpoint)


def _compare_courses(
    left: tuple[Course, ...],
    right: tuple[Course, ...],
    *,
    distance_tolerance: float,
) -> tuple[CourseComparison, ...]:
    comparisons: list[CourseComparison] = []
    for index in range(max(len(left), len(right))):
        left_course = left[index] if index < len(left) else None
        right_course = right[index] if index < len(right) else None
        left_distance = left_course.distance if left_course is not None else None
        right_distance = right_course.distance if right_course is not None else None
        difference = (
            None
            if left_distance is None or right_distance is None
            else abs(left_distance - right_distance)
        )
        comparisons.append(
            CourseComparison(
                index=index,
                left_bearing=None
                if left_course is None
                else left_course.bearing.canonical,
                right_bearing=None
                if right_course is None
                else right_course.bearing.canonical,
                bearing_equal=(
                    left_course is not None
                    and right_course is not None
                    and left_course.bearing.canonical == right_course.bearing.canonical
                ),
                left_distance=left_distance,
                right_distance=right_distance,
                distance_difference=difference,
                distance_equal=difference is not None
                and difference <= distance_tolerance,
            )
        )
    return tuple(comparisons)


def _documentary_equal(left: PTRRecord, right: PTRRecord) -> bool:
    return left.to_mapping() == right.to_mapping()


def _same_vertices(
    left: tuple[Point, ...],
    right: tuple[Point, ...],
    *,
    distance_tolerance: float,
) -> bool:
    if len(left) != len(right):
        return False
    return all(
        _point_distance(a, b) <= distance_tolerance
        for a, b in zip(left, right, strict=True)
    )


def _translate_points(
    points: tuple[Point, ...], dx: float, dy: float
) -> tuple[Point, ...]:
    return tuple(Point(point.x + dx, point.y + dy) for point in points)


def _centroid(points: tuple[Point, ...]) -> Point:
    if not points:
        return Point(0.0, 0.0)
    return Point(
        sum(point.x for point in points) / len(points),
        sum(point.y for point in points) / len(points),
    )


def _max_vertex_distance(
    left: tuple[Point, ...], right: tuple[Point, ...]
) -> float | None:
    if len(left) != len(right):
        return None
    return max(
        (_point_distance(a, b) for a, b in zip(left, right, strict=True)),
        default=0.0,
    )


def _hausdorff_distance(left: tuple[Point, ...], right: tuple[Point, ...]) -> float:
    return max(_directed_hausdorff(left, right), _directed_hausdorff(right, left))


def _directed_hausdorff(
    points: tuple[Point, ...], boundary: tuple[Point, ...]
) -> float:
    segments = tuple(zip(boundary, boundary[1:], strict=False))
    if not segments:
        return 0.0
    return max(
        min(_point_segment_distance(point, start, end) for start, end in segments)
        for point in points
    )


def _point_segment_distance(point: Point, start: Point, end: Point) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return _point_distance(point, start)
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_squared
    clamped = min(1.0, max(0.0, t))
    projected = Point(start.x + clamped * dx, start.y + clamped * dy)
    return _point_distance(point, projected)


def _point_distance(left: Point, right: Point) -> float:
    return hypot(left.x - right.x, left.y - right.y)


def _bounding_box(points: tuple[Point, ...]) -> BoundingBox:
    return BoundingBox(
        min(point.x for point in points),
        min(point.y for point in points),
        max(point.x for point in points),
        max(point.y for point in points),
    )


def _bbox_overlap(left: BoundingBox, right: BoundingBox) -> float:
    width = max(0.0, min(left.max_x, right.max_x) - max(left.min_x, right.min_x))
    height = max(0.0, min(left.max_y, right.max_y) - max(left.min_y, right.min_y))
    return width * height
