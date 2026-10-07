"""Smoke-test installed distribution contents, without importing checkout source."""

import sys
from importlib.util import find_spec

import ptr_core as core

assert "site-packages" in core.__file__, core.__file__
assert core.__version__ == sys.argv[1]
assert core.SUPPORTED_PTR_VERSIONS == ("0.1",)
assert not any(name.split(".")[0] in {"shapely", "pyproj"} for name in sys.modules)
text = "thence North, 10 m; thence East, 10 m; thence South, 10 m; thence West, 10 m;"
record = core.intake_parcel(text).record
assert record is not None and core.is_valid(record)
assert core.load_ptr_text(core.dumps_ptr(record)) == record
assert core.intake_parcel(core.to_technical_description(record).text).record == record
parcel = core.reconstruct(record)
assert parcel.metrics.area == 100 and parcel.metrics.perimeter == 40
assert parcel.metrics.closure.is_closed
assert core.to_geojson(parcel)["geometry"]["type"] == "Polygon"
assert core.to_wkt(parcel).startswith("POLYGON")
if sys.argv[2] == "base":
    assert find_spec("shapely") is None and find_spec("pyproj") is None
    try:
        core.analyze_topology(
            parcel, parcel, distance_tolerance=0.01, area_tolerance=0.01
        )
    except core.MissingOptionalDependencyError:
        pass
    else:
        raise AssertionError("Base wheel must report missing optional backend.")
else:
    assert core.analyze_topology(
        parcel, parcel, distance_tolerance=0.01, area_tolerance=0.01
    ).equal
    assert core.derive_courses_from_polygon(
        [(0, 0), (0, 10), (10, 10), (10, 0)], coordinate_frame="local-metres"
    ).lines
    assert (
        core.transform_crs(parcel, source_crs="EPSG:4326", target_crs="EPSG:3857").crs
        == "EPSG:3857"
    )
print(f"Installed wheel {core.__version__}: {sys.argv[2]} smoke passed")
