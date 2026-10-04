import pytest

import ptr_core
from ptr_core import PTRUnsupportedVersionError, load_ptr_mapping, validate


def test_public_api_exports_expected_v01_entry_points():
    expected = {
        "load_ptr",
        "load_ptr_text",
        "load_ptr_mapping",
        "dumps_ptr",
        "dump_ptr",
        "parse_bearing",
        "parse_course",
        "parse_distance",
        "parse_technical_description",
        "intake_parcel",
        "intake_candidate",
        "format_technical_description",
        "project_manual_table",
        "validate",
        "course_to_vector",
        "reconstruct",
        "compute_metrics",
        "qa_report",
        "to_geojson",
        "to_wkt",
        "georeference",
        "translate",
        "rotate",
        "transform_crs",
        "analyze_topology",
        "derive_courses_from_polygon",
    }

    assert expected <= set(ptr_core.__all__)
    assert ptr_core.SUPPORTED_PTR_VERSIONS == ("0.1",)
    assert ptr_core.__version__ == "0.1.1"


def test_unsupported_ptr_version_has_explicit_error_and_diagnostic():
    mapping = {"ptr_version": "0.2", "lines": [["N", 1], ["E", 1], ["S", 1]]}

    result = validate(mapping)

    assert not result.conforms
    assert result.errors[0].code == "unsupported_ptr_version"
    with pytest.raises(PTRUnsupportedVersionError):
        load_ptr_mapping(mapping)
