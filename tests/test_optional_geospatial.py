"""Exercise the public boundary in fresh processes without optional backends."""

import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize("missing", ["shapely", "pyproj", "both"])
def test_base_workflow_and_missing_backend_errors(missing):
    script = textwrap.dedent("""
        import importlib.abc
        import sys

        missing = sys.argv[1]
        blocked = {"shapely", "pyproj"} if missing == "both" else {missing}


        class NoBackend(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                name = fullname.split(".")[0]
                if name in blocked:
                    raise ModuleNotFoundError(
                        f"No module named {name!r}", name=name
                    )


        sys.meta_path.insert(0, NoBackend())
        import ptr_core as core

        assert not any(
            m.split(".")[0] in {"shapely", "pyproj"} for m in sys.modules
        )

        text = (
            "thence North, 10 m; thence East, 10 m; "
            "thence South, 10 m; thence West, 10 m;"
        )
        record = core.intake_parcel(text).record
        assert record is not None and core.is_valid(record)
        assert core.load_ptr_text(core.dumps_ptr(record)) == record
        assert core.parse_distance("1,000.25") == 1000.25
        assert core.parse_course("Due East", "10").distance == 10
        assert core.parse_technical_description(text).complete
        assert (
            core.intake_parcel(core.to_technical_description(record).text).record
            == record
        )
        assert (
            core.project_manual_table(record).to_ptr_mapping()
            == record.to_mapping()
        )
        parcel = core.reconstruct(record)
        assert core.compute_metrics(parcel).area == 100
        assert parcel.metrics.perimeter == 40 and parcel.metrics.closure.is_closed
        assert core.qa_report(record).conforms
        assert core.to_geojson(parcel)["geometry"]["type"] == "Polygon"
        assert core.to_wkt(parcel).startswith("POLYGON")
        moved = core.translate(parcel, dx=10, dy=0)
        assert (
            core.rotate(parcel, angle_degrees=0, origin=core.Point(0, 0)).vertices
            == parcel.vertices
        )
        assert core.compare_parcels(
            parcel, moved, distance_tolerance=0.01, area_tolerance=0.01
        ).compatible_frame
        tied = core.load_ptr_mapping(
            {**record.to_mapping(), "tie_point": "Control", "tie_line": ["E", 1]}
        )
        assert (
            core.georeference(
                core.reconstruct(tied), tie_point=core.Point(0, 0), crs="custom"
            ).crs
            == "custom"
        )

        calls = {
            "analyze_topology": (
                "shapely",
                lambda: core.analyze_topology(
                    parcel, parcel, distance_tolerance=0.01, area_tolerance=0.01
                ),
            ),
            "derive_courses_from_polygon": (
                "shapely",
                lambda: core.derive_courses_from_polygon(
                    [(0, 0), (0, 1), (1, 1)], coordinate_frame="local-metres"
                ),
            ),
            "transform_crs": (
                "pyproj",
                lambda: core.transform_crs(
                    parcel, source_crs="EPSG:4326", target_crs="EPSG:3857"
                ),
            ),
        }
        for capability, (dependency, call) in calls.items():
            if dependency not in blocked:
                continue
            try:
                call()
            except core.MissingOptionalDependencyError as exc:
                assert isinstance(exc, core.PTRError)
                assert isinstance(exc, ImportError)
                assert exc.dependency == dependency and exc.capability == capability
                assert "ptr-core[geospatial]" in str(exc)
            else:
                raise AssertionError(f"{capability} must require {dependency}")
        assert not any(m.split(".")[0] in blocked for m in sys.modules)
    """)
    result = subprocess.run(
        [sys.executable, "-c", script, missing], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_optional_loader_preserves_errors_inside_installed_backends(monkeypatch):
    from ptr_core.geospatial import _dependencies

    failure = ModuleNotFoundError("Broken backend dependency", name="backend_internal")

    def broken_import(module):
        raise failure

    monkeypatch.setattr(_dependencies, "import_module", broken_import)
    with pytest.raises(ModuleNotFoundError) as error:
        _dependencies.require_dependency("shapely", capability="analyze_topology")
    assert error.value is failure


def test_previous_module_imports_preserve_public_types_and_functions():
    import ptr_core
    from ptr_core.geometry_to_courses import (
        PTRCourseCandidate,
        derive_courses_from_polygon,
    )
    from ptr_core.topology import TopologyResult, analyze_topology
    from ptr_core.transforms import TransformedParcel, TransformError, transform_crs

    assert PTRCourseCandidate is ptr_core.PTRCourseCandidate
    assert derive_courses_from_polygon is ptr_core.derive_courses_from_polygon
    assert TopologyResult is ptr_core.TopologyResult
    assert analyze_topology is ptr_core.analyze_topology
    assert TransformError is ptr_core.TransformError
    assert TransformedParcel is ptr_core.TransformedParcel
    assert transform_crs is ptr_core.transform_crs
