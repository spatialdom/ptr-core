"""Parcel topology primitives backed by Shapely/GEOS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shapely.geometry import LineString, Polygon

from ptr_core.geometry import DerivedParcel, Point
from ptr_core.georeferencing import GeoreferencedParcel
from ptr_core.transforms import TransformedParcel

TopologyParcel = DerivedParcel | GeoreferencedParcel | TransformedParcel


@dataclass(frozen=True, slots=True)
class TopologyResult:
    compatible_frame: bool
    frame_reason: str
    crs: str | None
    relationship: str
    equal: bool | None
    contains: bool | None
    within: bool | None
    touches: bool | None
    point_touch: bool | None
    edge_adjacent: bool | None
    overlaps: bool | None
    overlap_area: float | None
    shared_boundary_length: float | None
    shared_boundary_wkt: str | None
    gap_distance: float | None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "compatible_frame": self.compatible_frame,
            "frame_reason": self.frame_reason,
            "crs": self.crs,
            "relationship": self.relationship,
            "equal": self.equal,
            "contains": self.contains,
            "within": self.within,
            "touches": self.touches,
            "point_touch": self.point_touch,
            "edge_adjacent": self.edge_adjacent,
            "overlaps": self.overlaps,
            "overlap_area": self.overlap_area,
            "shared_boundary_length": self.shared_boundary_length,
            "shared_boundary_wkt": self.shared_boundary_wkt,
            "gap_distance": self.gap_distance,
        }


@dataclass(frozen=True, slots=True)
class _Frame:
    compatible: bool
    reason: str
    crs: str | None


def analyze_topology(
    left: TopologyParcel,
    right: TopologyParcel,
    *,
    distance_tolerance: float,
    area_tolerance: float,
) -> TopologyResult:
    """Analyze parcel topology in compatible local or referenced coordinates."""

    frame = _frame_compatibility(left, right)
    if not frame.compatible:
        return TopologyResult(
            compatible_frame=False,
            frame_reason=frame.reason,
            crs=frame.crs,
            relationship="incompatible_frame",
            equal=None,
            contains=None,
            within=None,
            touches=None,
            point_touch=None,
            edge_adjacent=None,
            overlaps=None,
            overlap_area=None,
            shared_boundary_length=None,
            shared_boundary_wkt=None,
            gap_distance=None,
        )

    left_polygon = _polygon(left)
    right_polygon = _polygon(right)
    intersection = left_polygon.intersection(right_polygon)
    shared_boundary = left_polygon.boundary.intersection(right_polygon.boundary)
    shared_length = float(shared_boundary.length)
    gap_distance = float(left_polygon.distance(right_polygon))
    overlap_area = float(intersection.area)
    equal = (
        left_polygon.hausdorff_distance(right_polygon) <= distance_tolerance
        and float(left_polygon.symmetric_difference(right_polygon).area)
        <= area_tolerance
    )
    contains = left_polygon.covers(right_polygon) and not equal
    within = right_polygon.covers(left_polygon) and not equal
    touches = left_polygon.touches(right_polygon) or (
        0 < gap_distance <= distance_tolerance
    )
    edge_adjacent = shared_length > distance_tolerance
    point_touch = bool(touches and not edge_adjacent and not intersection.is_empty)
    overlaps = (
        overlap_area > area_tolerance and not contains and not within and not equal
    )
    relationship = _relationship(
        equal=equal,
        contains=contains,
        within=within,
        overlaps=overlaps,
        edge_adjacent=edge_adjacent,
        point_touch=point_touch,
        gap_distance=gap_distance,
        distance_tolerance=distance_tolerance,
    )

    return TopologyResult(
        compatible_frame=True,
        frame_reason=frame.reason,
        crs=frame.crs,
        relationship=relationship,
        equal=equal,
        contains=contains,
        within=within,
        touches=bool(touches),
        point_touch=point_touch,
        edge_adjacent=edge_adjacent,
        overlaps=overlaps,
        overlap_area=overlap_area,
        shared_boundary_length=shared_length,
        shared_boundary_wkt=None if shared_boundary.is_empty else shared_boundary.wkt,
        gap_distance=gap_distance,
    )


def _relationship(
    *,
    equal: bool,
    contains: bool,
    within: bool,
    overlaps: bool,
    edge_adjacent: bool,
    point_touch: bool,
    gap_distance: float,
    distance_tolerance: float,
) -> str:
    if equal:
        return "equal"
    if contains:
        return "contains"
    if within:
        return "within"
    if overlaps:
        return "overlap"
    if edge_adjacent:
        return "edge_adjacent"
    if point_touch:
        return "point_touch"
    if 0 < gap_distance <= distance_tolerance:
        return "near_gap"
    return "disjoint"


def _polygon(parcel: TopologyParcel) -> Polygon:
    points = list(parcel.vertices)
    if not _same_point(points[-1], parcel.final_endpoint):
        points.append(parcel.final_endpoint)
    if not _same_point(points[-1], points[0]):
        points.append(points[0])
    ring = LineString([(point.x, point.y) for point in points])
    return Polygon(ring)


def _same_point(left: Point, right: Point, tolerance: float = 1e-12) -> bool:
    return abs(left.x - right.x) <= tolerance and abs(left.y - right.y) <= tolerance


def _frame_compatibility(left: TopologyParcel, right: TopologyParcel) -> _Frame:
    left_crs = _crs(left)
    right_crs = _crs(right)
    if left_crs is not None and right_crs is not None:
        if left_crs == right_crs:
            return _Frame(True, "same_crs", left_crs)
        return _Frame(False, "different_crs", None)
    if left_crs is None and right_crs is None:
        return _Frame(True, "local_unreferenced", None)
    return _Frame(False, "mixed_local_and_georeferenced", None)


def _crs(parcel: TopologyParcel) -> str | None:
    if isinstance(parcel, GeoreferencedParcel | TransformedParcel):
        return parcel.crs
    return None
