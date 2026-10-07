from importlib.util import find_spec

import pytest

from ptr_core import (
    Point,
    analyze_topology,
    compare_parcels,
    georeference,
    load_ptr_mapping,
    reconstruct,
    rotate,
    to_geojson,
    transform_crs,
    translate,
)
from ptr_core.transforms import TransformError


def _square():
    return reconstruct(
        load_ptr_mapping(
            {
                "ptr_version": "0.1",
                "lines": [["N", 10.0], ["E", 10.0], ["S", 10.0], ["W", 10.0]],
            }
        )
    )


def _tied_square():
    return reconstruct(
        load_ptr_mapping(
            {
                "ptr_version": "0.1",
                "tie_point": "Control",
                "tie_line": ["E", 1.0],
                "lines": [["N", 10.0], ["E", 10.0], ["S", 10.0], ["W", 10.0]],
            }
        )
    )


def test_translate_returns_separate_reversible_geometry():
    parcel = _square()
    moved = translate(parcel, dx=3.0, dy=-4.0)
    restored = translate(moved, dx=-3.0, dy=4.0)

    assert parcel.vertices[0] == Point(0.0, 0.0)
    assert moved.vertices[0] == Point(3.0, -4.0)
    assert restored.vertices == parcel.vertices
    assert restored.final_endpoint == parcel.final_endpoint
    assert [step.operation for step in restored.transform_steps] == [
        "translate",
        "translate",
    ]
    assert moved.local is parcel


def test_rotate_around_explicit_origin_is_reversible():
    parcel = _square()
    rotated = rotate(parcel, angle_degrees=90.0, origin=Point(0.0, 0.0))
    restored = rotate(rotated, angle_degrees=-90.0, origin=Point(0.0, 0.0))

    assert rotated.vertices[1].x == pytest.approx(-10.0)
    assert rotated.vertices[1].y == pytest.approx(0.0)
    for actual, expected in zip(restored.vertices, parcel.vertices, strict=True):
        assert actual.x == pytest.approx(expected.x, abs=1e-9)
        assert actual.y == pytest.approx(expected.y, abs=1e-9)


def test_transform_crs_requires_explicit_source_and_target_crs():
    parcel = _square()

    with pytest.raises(TransformError):
        transform_crs(parcel, source_crs="", target_crs="EPSG:3857")
    with pytest.raises(TransformError):
        transform_crs(parcel, source_crs="EPSG:4326", target_crs="")


@pytest.mark.skipif(find_spec("pyproj") is None, reason="Requires geospatial extra")
def test_transform_crs_uses_explicit_crs_and_is_reversible():
    parcel = georeference(
        _tied_square(),
        tie_point=Point(0.0, 0.0),
        crs="EPSG:4326",
    )

    projected = transform_crs(
        parcel,
        source_crs="EPSG:4326",
        target_crs="EPSG:3857",
    )
    restored = transform_crs(
        projected,
        source_crs="EPSG:3857",
        target_crs="EPSG:4326",
    )

    assert projected.crs == "EPSG:3857"
    assert projected.vertices[0].x == pytest.approx(111319.49079327357)
    assert projected.transform_steps[-1].to_mapping()["parameters"] == {
        "source_crs": "EPSG:4326",
        "target_crs": "EPSG:3857",
    }
    assert restored.crs == "EPSG:4326"
    assert restored.vertices[0].x == pytest.approx(parcel.vertices[0].x, abs=1e-9)
    assert restored.vertices[0].y == pytest.approx(parcel.vertices[0].y, abs=1e-9)


def test_transform_crs_rejects_conflicting_parcel_crs_metadata():
    parcel = georeference(
        _tied_square(),
        tie_point=Point(0.0, 0.0),
        crs="EPSG:4326",
    )

    with pytest.raises(TransformError):
        transform_crs(parcel, source_crs="EPSG:3857", target_crs="EPSG:4326")


@pytest.mark.skipif(find_spec("shapely") is None, reason="Requires geospatial extra")
def test_transformed_geometry_integrates_with_export_topology_and_comparison():
    parcel = _square()
    moved = translate(parcel, dx=10.0, dy=0.0)

    feature = to_geojson(moved)
    topology = analyze_topology(
        parcel,
        moved,
        distance_tolerance=0.01,
        area_tolerance=0.01,
    )
    comparison = compare_parcels(
        parcel,
        moved,
        distance_tolerance=0.01,
        area_tolerance=0.01,
    )

    assert feature["properties"]["transforms"][0]["operation"] == "translate"
    assert topology.relationship == "edge_adjacent"
    assert comparison.geometry_equal is False
    assert comparison.geometry_equivalent_by_translation is True
