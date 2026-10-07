import pytest

from ptr_core import (
    GeometryToCoursesError,
    derive_courses_from_polygon,
    load_ptr_mapping,
    reconstruct,
)

shapely_geometry = pytest.importorskip("shapely.geometry")
MultiPolygon = shapely_geometry.MultiPolygon
Polygon = shapely_geometry.Polygon


def test_derives_clockwise_ptr_courses_from_simple_polygon():
    candidate = derive_courses_from_polygon(
        [(0.0, 0.0), (0.0, 10.0), (20.0, 10.0), (20.0, 0.0)],
        coordinate_frame="local-metres",
    )

    assert [course.to_json_value() for course in candidate.lines] == [
        ["N", 10.0],
        ["E", 20.0],
        ["S", 10.0],
        ["W", 20.0],
    ]
    assert candidate.to_mapping() == {
        "ptr_version": "0.1",
        "lines": [["N", 10.0], ["E", 20.0], ["S", 10.0], ["W", 20.0]],
    }
    assert candidate.to_metadata()["bearing_precision"] == "nearest_second"


def test_counterclockwise_input_is_reordered_to_ptr_clockwise_convention():
    candidate = derive_courses_from_polygon(
        [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0)],
        coordinate_frame="local-metres",
    )

    assert [course.bearing.canonical for course in candidate.lines] == [
        "N",
        "E",
        "S",
        "W",
    ]
    assert candidate.winding == "clockwise"


def test_produces_canonical_quadrant_bearings_and_rounded_distances():
    candidate = derive_courses_from_polygon(
        [(0.0, 0.0), (10.0, 10.0), (20.0, 0.0)],
        coordinate_frame="local-metres",
        distance_decimals=4,
    )

    assert [course.to_json_value() for course in candidate.lines] == [
        ["N45-00E", 14.1421],
        ["S45-00E", 14.1421],
        ["W", 20.0],
    ]


def test_roundtrip_geometry_to_courses_to_reconstruction_with_explicit_tolerance():
    candidate = derive_courses_from_polygon(
        [(0.0, 0.0), (0.0, 10.0), (20.0, 10.0), (20.0, 0.0)],
        coordinate_frame="local-metres",
    )
    record = load_ptr_mapping(candidate.to_mapping())
    parcel = reconstruct(record)

    assert parcel.metrics.area == pytest.approx(200.0)
    assert parcel.metrics.closure.linear == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize(
    "geometry",
    [
        Polygon(
            [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)],
            holes=[[(2.0, 2.0), (4.0, 2.0), (4.0, 4.0), (2.0, 4.0)]],
        ),
        Polygon([(0.0, 0.0), (10.0, 10.0), (0.0, 10.0), (10.0, 0.0)]),
        MultiPolygon(
            [
                Polygon([(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]),
                Polygon([(2.0, 0.0), (2.0, 1.0), (3.0, 1.0), (3.0, 0.0)]),
            ]
        ),
    ],
)
def test_rejects_unsupported_geometry(geometry):
    with pytest.raises(GeometryToCoursesError):
        derive_courses_from_polygon(geometry, coordinate_frame="local-metres")


def test_requires_known_metric_coordinate_frame():
    with pytest.raises(GeometryToCoursesError):
        derive_courses_from_polygon(
            [(0.0, 0.0), (0.0, 10.0), (20.0, 10.0), (20.0, 0.0)],
            coordinate_frame="",
        )
