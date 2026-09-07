import json

import pytest

from ptr_core import (
    GeoreferencingError,
    Point,
    georeference,
    load_ptr_mapping,
    qa_report,
    reconstruct,
    to_geojson,
    to_wkt,
)


def test_qa_report_combines_validation_metrics_and_findings():
    report = qa_report(
        {
            "ptr_version": "0.1",
            "declared_area": 7500.0,
            "lines": [["N", 100.0], ["E", 80.0], ["S", 100.0], ["W", 79.5]],
        }
    )
    data = report.to_mapping()

    assert data["conforms"] is True
    assert data["metrics"]["closure"]["linear"] == 0.5
    assert data["metrics"]["area"] == 8000.0
    assert data["metrics"]["declared_area_comparison"]["absolute_difference"] == 500.0
    assert [finding["code"] for finding in data["findings"]] == [
        "misclosure",
        "declared_area_difference",
    ]
    json.dumps(data)


def test_qa_report_preserves_validation_error_category_without_geometry():
    report = qa_report({"ptr_version": "0.1"})
    data = report.to_mapping()

    assert data["conforms"] is False
    assert data["metrics"] is None
    assert data["findings"][0]["layer"] == "structural"
    assert data["findings"][0]["code"] == "missing_lines"


def test_exports_local_geojson_and_wkt_with_closed_ccw_ring():
    parcel = reconstruct(
        load_ptr_mapping(
            {
                "ptr_version": "0.1",
                "name": "Rectangle",
                "record_id": "rect-1",
                "lines": [["N", 100.0], ["E", 80.0], ["S", 100.0], ["W", 80.0]],
            }
        )
    )

    feature = to_geojson(parcel)
    ring = feature["geometry"]["coordinates"][0]

    assert feature["type"] == "Feature"
    assert feature["properties"]["georeferenced"] is False
    assert feature["properties"]["name"] == "Rectangle"
    assert ring[0] == ring[-1]
    assert ring == [[0.0, 0.0], [80.0, 0.0], [80.0, 100.0], [0.0, 100.0], [0.0, 0.0]]
    assert to_wkt(parcel) == "POLYGON ((0 0, 80 0, 80 100, 0 100, 0 0))"
    json.dumps(feature)


def test_exports_nonclosing_traverse_with_explicit_export_closure():
    parcel = reconstruct(
        load_ptr_mapping(
            {
                "ptr_version": "0.1",
                "lines": [["N", 100.0], ["E", 80.0], ["S", 100.0], ["W", 79.5]],
            }
        )
    )

    ring = to_geojson(parcel)["geometry"]["coordinates"][0]

    assert parcel.final_endpoint == Point(0.5, 0.0)
    assert ring[0] == ring[-1]
    assert [0.5, 0.0] in ring


def test_georeference_requires_explicit_crs_and_tie_line():
    parcel = reconstruct(
        load_ptr_mapping(
            {
                "ptr_version": "0.1",
                "lines": [["N", 10.0], ["E", 10.0], ["S45-00W", 14.1421356237]],
            }
        )
    )

    with pytest.raises(GeoreferencingError):
        georeference(parcel, tie_point=Point(500_000.0, 1_600_000.0), crs="EPSG:32651")

    tied = reconstruct(
        load_ptr_mapping(
            {
                "ptr_version": "0.1",
                "tie_point": "BLLM",
                "tie_line": ["E", 25.0],
                "lines": [["N", 10.0], ["E", 10.0], ["S45-00W", 14.1421356237]],
            }
        )
    )
    with pytest.raises(GeoreferencingError):
        georeference(tied, tie_point=Point(0.0, 0.0), crs="")


@pytest.mark.parametrize(
    ("tie_line", "expected_point1"),
    [
        (["N", 10.0], Point(100.0, 210.0)),
        (["E", 10.0], Point(110.0, 200.0)),
        (["S", 10.0], Point(100.0, 190.0)),
        (["W", 10.0], Point(90.0, 200.0)),
        (["N45-00E", 10.0], Point(107.07106781186548, 207.07106781186548)),
        (["S45-00E", 10.0], Point(107.07106781186548, 192.92893218813452)),
        (["S45-00W", 10.0], Point(92.92893218813452, 192.92893218813452)),
        (["N45-00W", 10.0], Point(92.92893218813452, 207.07106781186548)),
    ],
)
def test_georeference_applies_tie_line_quadrants(tie_line, expected_point1):
    parcel = reconstruct(
        load_ptr_mapping(
            {
                "ptr_version": "0.1",
                "tie_point": "Control",
                "tie_line": tie_line,
                "lines": [["N", 10.0], ["E", 10.0], ["S45-00W", 14.1421356237]],
            }
        )
    )

    referenced = georeference(
        parcel,
        tie_point=Point(100.0, 200.0),
        crs="EPSG:32651",
    )

    assert referenced.point1.x == pytest.approx(expected_point1.x)
    assert referenced.point1.y == pytest.approx(expected_point1.y)
    assert referenced.vertices[0] == referenced.point1
    assert referenced.local.vertices[0] == Point(0.0, 0.0)
    assert to_geojson(referenced)["properties"]["crs"] == "EPSG:32651"
