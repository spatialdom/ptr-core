import json

import pytest

from ptr_core import (
    Point,
    analyze_topology,
    georeference,
    load_ptr_mapping,
    reconstruct,
)

pytest.importorskip("shapely")


def _rectangle(width: float, height: float, *, point1: Point, crs: str = "EPSG:32651"):
    record = load_ptr_mapping(
        {
            "ptr_version": "0.1",
            "tie_point": "Control",
            "tie_line": ["E", 1.0],
            "lines": [["N", height], ["E", width], ["S", height], ["W", width]],
        }
    )
    return georeference(
        reconstruct(record),
        tie_point=Point(point1.x - 1.0, point1.y),
        crs=crs,
    )


def test_topology_requires_compatible_coordinate_frames():
    local = reconstruct(
        load_ptr_mapping(
            {
                "ptr_version": "0.1",
                "lines": [["N", 10.0], ["E", 10.0], ["S", 10.0], ["W", 10.0]],
            }
        )
    )
    referenced = _rectangle(10.0, 10.0, point1=Point(0.0, 0.0))

    result = analyze_topology(
        local,
        referenced,
        distance_tolerance=0.01,
        area_tolerance=0.01,
    )

    assert result.compatible_frame is False
    assert result.relationship == "incompatible_frame"
    assert result.frame_reason == "mixed_local_and_georeferenced"
    assert result.overlap_area is None


def test_exact_edge_adjacency_reports_shared_boundary_length():
    left = _rectangle(10.0, 10.0, point1=Point(0.0, 0.0))
    right = _rectangle(5.0, 10.0, point1=Point(10.0, 0.0))

    result = analyze_topology(
        left,
        right,
        distance_tolerance=0.01,
        area_tolerance=0.01,
    )

    assert result.compatible_frame
    assert result.relationship == "edge_adjacent"
    assert result.edge_adjacent is True
    assert result.point_touch is False
    assert result.shared_boundary_length == pytest.approx(10.0)
    assert result.overlap_area == 0.0
    assert result.shared_boundary_wkt is not None
    json.dumps(result.to_mapping())


def test_point_touch_is_distinct_from_shared_edge_adjacency():
    left = _rectangle(10.0, 10.0, point1=Point(0.0, 0.0))
    right = _rectangle(5.0, 5.0, point1=Point(10.0, 10.0))

    result = analyze_topology(
        left,
        right,
        distance_tolerance=0.01,
        area_tolerance=0.01,
    )

    assert result.relationship == "point_touch"
    assert result.touches is True
    assert result.point_touch is True
    assert result.edge_adjacent is False
    assert result.shared_boundary_length == 0.0


def test_overlap_and_containment_report_metric_area():
    base = _rectangle(10.0, 10.0, point1=Point(0.0, 0.0))
    overlapping = _rectangle(10.0, 10.0, point1=Point(5.0, 0.0))
    contained = _rectangle(4.0, 4.0, point1=Point(2.0, 2.0))

    overlap = analyze_topology(
        base,
        overlapping,
        distance_tolerance=0.01,
        area_tolerance=0.01,
    )
    containment = analyze_topology(
        base,
        contained,
        distance_tolerance=0.01,
        area_tolerance=0.01,
    )

    assert overlap.relationship == "overlap"
    assert overlap.overlaps is True
    assert overlap.overlap_area == pytest.approx(50.0)
    assert containment.relationship == "contains"
    assert containment.contains is True
    assert containment.overlap_area == pytest.approx(16.0)


def test_small_gap_and_unrelated_parcels_report_distance():
    left = _rectangle(10.0, 10.0, point1=Point(0.0, 0.0))
    near = _rectangle(5.0, 10.0, point1=Point(10.005, 0.0))
    far = _rectangle(5.0, 10.0, point1=Point(25.0, 0.0))

    near_result = analyze_topology(
        left,
        near,
        distance_tolerance=0.01,
        area_tolerance=0.01,
    )
    far_result = analyze_topology(
        left,
        far,
        distance_tolerance=0.01,
        area_tolerance=0.01,
    )

    assert near_result.relationship == "near_gap"
    assert near_result.gap_distance == pytest.approx(0.005)
    assert near_result.touches is True
    assert far_result.relationship == "disjoint"
    assert far_result.gap_distance == pytest.approx(15.0)
    assert far_result.touches is False


def test_duplicate_equivalent_geometry_check_uses_tolerances():
    left = _rectangle(10.0, 10.0, point1=Point(0.0, 0.0))
    almost = _rectangle(10.0005, 10.0, point1=Point(0.0, 0.0))

    result = analyze_topology(
        left,
        almost,
        distance_tolerance=0.001,
        area_tolerance=0.01,
    )

    assert result.relationship == "equal"
    assert result.equal is True
    assert result.overlap_area == pytest.approx(100.0)


def test_different_referenced_crs_is_not_spatially_compared():
    left = _rectangle(10.0, 10.0, point1=Point(0.0, 0.0), crs="EPSG:32651")
    right = _rectangle(10.0, 10.0, point1=Point(0.0, 0.0), crs="EPSG:4326")

    result = analyze_topology(
        left,
        right,
        distance_tolerance=0.01,
        area_tolerance=0.01,
    )

    assert result.compatible_frame is False
    assert result.frame_reason == "different_crs"
