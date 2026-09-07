import pytest

from ptr_core import (
    Course,
    Point,
    compute_metrics,
    course_to_vector,
    load_ptr_mapping,
    parse_bearing,
    reconstruct,
)

TOLERANCE = 1e-9


@pytest.mark.parametrize(
    ("bearing", "expected"),
    [
        ("N", (0.0, 10.0)),
        ("E", (10.0, 0.0)),
        ("S", (0.0, -10.0)),
        ("W", (-10.0, 0.0)),
        (
            "N45-00E",
            (pytest.approx(7.071067811865475), pytest.approx(7.071067811865475)),
        ),
        (
            "S45-00E",
            (pytest.approx(7.071067811865475), pytest.approx(-7.071067811865475)),
        ),
        (
            "S45-00W",
            (pytest.approx(-7.071067811865475), pytest.approx(-7.071067811865475)),
        ),
        (
            "N45-00W",
            (pytest.approx(-7.071067811865475), pytest.approx(7.071067811865475)),
        ),
    ],
)
def test_course_to_vector_covers_cardinals_and_quadrants(bearing, expected):
    vector = course_to_vector(Course(parse_bearing(bearing), 10.0))

    assert vector.dx == expected[0]
    assert vector.dy == expected[1]


def test_reconstructs_clockwise_rectangle_vertices_and_metrics():
    record = load_ptr_mapping(
        {
            "ptr_version": "0.1",
            "name": "Rectangle",
            "declared_area": 8000.0,
            "lines": [["N", 100.0], ["E", 80.0], ["S", 100.0], ["W", 80.0]],
        }
    )

    parcel = reconstruct(record)

    assert parcel.origin == Point(0.0, 0.0)
    assert parcel.vertices == (
        Point(0.0, 0.0),
        Point(0.0, 100.0),
        Point(80.0, 100.0),
        Point(80.0, 0.0),
    )
    assert parcel.final_endpoint == Point(0.0, 0.0)
    assert parcel.metrics.closure.is_closed
    assert parcel.metrics.closure.linear == 0.0
    assert parcel.metrics.perimeter == 360.0
    assert parcel.metrics.area == 8000.0
    assert parcel.metrics.signed_area == -8000.0
    assert parcel.metrics.declared_area_comparison is not None
    assert parcel.metrics.declared_area_comparison.absolute_difference == 0.0
    assert parcel.qa_findings == ()


def test_reconstruct_applies_source_order_without_snapping_nonclosing_endpoint():
    record = load_ptr_mapping(
        {
            "ptr_version": "0.1",
            "name": "Non-closing parcel",
            "lines": [["N", 100.0], ["E", 80.0], ["S", 100.0], ["W", 79.5]],
        }
    )

    parcel = reconstruct(record)

    assert parcel.vertices[-1] == Point(80.0, 0.0)
    assert parcel.final_endpoint == Point(0.5, 0.0)
    assert parcel.metrics.closure.east == 0.5
    assert parcel.metrics.closure.north == 0.0
    assert parcel.metrics.closure.linear == 0.5
    assert not parcel.metrics.closure.is_closed
    assert _codes(parcel) == {"misclosure"}


def test_small_misclosure_uses_configurable_tolerance():
    record = load_ptr_mapping(
        {
            "ptr_version": "0.1",
            "lines": [["N", 1.0], ["E", 1.0], ["S", 1.0], ["W", 0.999]],
        }
    )

    near_closed = reconstruct(record, closure_tolerance=0.01)
    strict = reconstruct(record, closure_tolerance=0.0001)

    assert near_closed.metrics.closure.linear == pytest.approx(0.001)
    assert near_closed.metrics.closure.is_closed
    assert "misclosure" not in _codes(near_closed)
    assert "misclosure" in _codes(strict)


def test_counterclockwise_order_is_geometric_qa_not_invalidity():
    record = load_ptr_mapping(
        {
            "ptr_version": "0.1",
            "name": "Counterclockwise parcel",
            "lines": [["E", 80.0], ["N", 100.0], ["W", 80.0], ["S", 100.0]],
        }
    )

    parcel = reconstruct(record)

    assert parcel.metrics.area == 8000.0
    assert parcel.metrics.signed_area == 8000.0
    assert "counterclockwise_orientation" in _codes(parcel)


def test_area_comparison_never_overwrites_declared_area():
    record = load_ptr_mapping(
        {
            "ptr_version": "0.1",
            "declared_area": 7500.0,
            "lines": [["N", 100.0], ["E", 80.0], ["S", 100.0], ["W", 80.0]],
        }
    )

    metrics = compute_metrics(reconstruct(record))

    assert record.declared_area == 7500.0
    assert metrics.area == 8000.0
    assert metrics.declared_area_comparison is not None
    assert metrics.declared_area_comparison.absolute_difference == 500.0
    assert metrics.declared_area_comparison.relative_difference == pytest.approx(1 / 15)


def test_degenerate_and_self_intersecting_cases_are_flagged():
    degenerate = reconstruct(
        load_ptr_mapping(
            {
                "ptr_version": "0.1",
                "lines": [["N", 10.0], ["S", 5.0], ["S", 5.0]],
            }
        )
    )
    crossing = reconstruct(
        load_ptr_mapping(
            {
                "ptr_version": "0.1",
                "name": "Self-intersecting parcel",
                "lines": [
                    ["N45-00E", 100.0],
                    ["S45-00E", 100.0],
                    ["N45-00W", 100.0],
                    ["S45-00W", 100.0],
                ],
            }
        )
    )

    assert "degenerate_area" in _codes(degenerate)
    assert {"duplicate_vertex", "self_intersection"} & _codes(crossing)


def _codes(parcel):
    return {finding.code for finding in parcel.qa_findings}
