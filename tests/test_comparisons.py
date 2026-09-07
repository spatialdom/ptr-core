import pytest

from ptr_core import (
    Point,
    compare_parcels,
    georeference,
    load_ptr_mapping,
    reconstruct,
)


def _parcel(lines, *, tie_line=None, declared_area=None):
    mapping = {
        "ptr_version": "0.1",
        "tie_point": "Control",
        "lines": lines,
    }
    if tie_line is not None:
        mapping["tie_line"] = tie_line
    if declared_area is not None:
        mapping["declared_area"] = declared_area
    return reconstruct(load_ptr_mapping(mapping))


def test_compare_identical_local_parcels():
    left = _parcel([["N", 10.0], ["E", 10.0], ["S45-00W", 14.1421356237]])
    right = _parcel([["N", 10.0], ["E", 10.0], ["S45-00W", 14.1421356237]])

    result = compare_parcels(
        left,
        right,
        distance_tolerance=1e-9,
        area_tolerance=1e-9,
    )

    assert result.compatible_frame
    assert result.frame_reason == "local_unreferenced"
    assert result.documentary_equal
    assert result.geometry_equal is True
    assert result.geometry_equivalent_by_translation is True
    assert result.area_difference == 0.0
    assert result.perimeter_difference == 0.0
    assert result.max_vertex_distance == 0.0
    assert result.hausdorff_distance == 0.0


def test_compare_translated_georeferenced_parcels_separates_shape_and_position():
    local = _parcel(
        [["N", 10.0], ["E", 10.0], ["S45-00W", 14.1421356237]],
        tie_line=["E", 0.01],
    )
    left = georeference(local, tie_point=Point(100.0, 200.0), crs="EPSG:32651")
    right = georeference(local, tie_point=Point(103.0, 204.0), crs="EPSG:32651")

    result = compare_parcels(
        left,
        right,
        distance_tolerance=1e-9,
        area_tolerance=1e-9,
    )

    assert result.compatible_frame
    assert result.crs == "EPSG:32651"
    assert result.geometry_equal is False
    assert result.geometry_equivalent_by_translation is True
    assert result.centroid_translation is not None
    assert result.centroid_translation.dx == pytest.approx(3.0)
    assert result.centroid_translation.dy == pytest.approx(4.0)
    assert result.centroid_distance == pytest.approx(5.0)


def test_compare_slightly_different_parcels_uses_explicit_tolerance():
    left = _parcel([["N", 10.0], ["E", 10.0], ["S45-00W", 14.1421356237]])
    right = _parcel([["N", 10.0], ["E", 10.0005], ["S45-00W", 14.1421356237]])

    loose = compare_parcels(
        left,
        right,
        distance_tolerance=0.001,
        area_tolerance=0.001,
    )
    strict = compare_parcels(
        left,
        right,
        distance_tolerance=0.0001,
        area_tolerance=0.0001,
    )

    assert loose.course_comparisons[1].distance_equal
    assert loose.geometry_equal is True
    assert strict.course_comparisons[1].distance_equal is False
    assert strict.geometry_equal is False
    assert strict.area_difference > 0.0


def test_compare_clearly_different_parcels_reports_metrics():
    left = _parcel([["N", 10.0], ["E", 10.0], ["S45-00W", 14.1421356237]])
    right = _parcel([["N", 20.0], ["E", 20.0], ["S45-00W", 28.2842712474]])

    result = compare_parcels(
        left,
        right,
        distance_tolerance=1e-9,
        area_tolerance=1e-9,
    )

    assert result.documentary_equal is False
    assert result.geometry_equal is False
    assert result.geometry_equivalent_by_translation is False
    assert result.area_difference == pytest.approx(150.0)
    assert result.perimeter_difference == pytest.approx(34.1421356237)
    assert result.bounding_box_overlap_area == pytest.approx(100.0)


def test_compare_incompatible_frames_limits_spatial_metrics():
    local = _parcel(
        [["N", 10.0], ["E", 10.0], ["S45-00W", 14.1421356237]],
        tie_line=["E", 1.0],
    )
    referenced = georeference(local, tie_point=Point(0.0, 0.0), crs="EPSG:32651")
    other_crs = georeference(local, tie_point=Point(0.0, 0.0), crs="EPSG:4326")

    mixed = compare_parcels(
        local,
        referenced,
        distance_tolerance=1e-9,
        area_tolerance=1e-9,
    )
    different_crs = compare_parcels(
        referenced,
        other_crs,
        distance_tolerance=1e-9,
        area_tolerance=1e-9,
    )

    assert mixed.compatible_frame is False
    assert mixed.frame_reason == "mixed_local_and_georeferenced"
    assert mixed.geometry_equal is None
    assert mixed.centroid_distance is None
    assert different_crs.compatible_frame is False
    assert different_crs.frame_reason == "different_crs"
