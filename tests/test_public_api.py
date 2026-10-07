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
        "ParcelInput",
        "IntakeResult",
        "format_technical_description",
        "to_technical_description",
        "project_manual_table",
        "validate",
        "is_valid",
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


def test_schema_specific_protocol_is_not_public():
    assert "CandidateMapping" not in ptr_core.__all__
    assert not hasattr(ptr_core, "CandidateMapping")


@pytest.mark.parametrize(
    "source,expected",
    [
        ({"ptr_version": "0.1", "lines": [["N", 10], ["E", 10], ["S", 5]]}, True),
        ('{"ptr_version":"0.1","lines":[["N",10],["E",10],["S",5]]}', True),
        (
            load_ptr_mapping(
                {"ptr_version": "0.1", "lines": [["N", 10], ["E", 10], ["S", 5]]}
            ),
            True,
        ),
        ("{broken", False),
        ("[]", False),
        ({"ptr_version": "0.2", "lines": [["N", 1]]}, False),
        ({"ptr_version": "0.1", "lines": [["North", 10]] * 3}, False),
        ({"ptr_version": "0.1", "lines": [["N", float("nan")]] * 3}, False),
        (None, False),
    ],
)
def test_boolean_conformance_accepts_validation_inputs(source, expected):
    assert ptr_core.is_valid(source) is expected
    assert ptr_core.validate(source).conforms is expected


def test_boolean_conformance_does_not_require_geometric_closure():
    record = load_ptr_mapping(
        {"ptr_version": "0.1", "lines": [["N", 10], ["E", 10], ["S", 5]]}
    )
    assert ptr_core.is_valid(record)
    assert any(d.code == "misclosure" for d in ptr_core.reconstruct(record).qa_findings)


def test_generated_description_alias_preserves_plotter_review_contract():
    record = load_ptr_mapping(
        {
            "ptr_version": "0.1",
            "name": "Synthetic parcel",
            "lines": [["N", 10], ["E", 10], ["S", 10], ["W", 10]],
            "tie_point": "Monument",
            "tie_line": ["W", 25],
            "declared_area": 100,
        }
    )
    assert ptr_core.format_technical_description is ptr_core.to_technical_description
    generated = ptr_core.to_technical_description(record)
    assert isinstance(generated, ptr_core.GeneratedDescription)
    assert generated.text.startswith("Generated technical description.\n")
    assert generated.omitted_fields == ("name",)
    assert generated.diagnostics[0].code == "metadata_not_in_prose"
    # Parcel Plotter consumes these attributes and table metadata independently.
    table = ptr_core.project_manual_table(record).to_mapping()
    restored = ptr_core.intake_parcel(generated.text).record
    assert restored.lines == record.lines
    assert restored.tie_line == record.tie_line
    assert restored.declared_area == record.declared_area
    assert table["metadata"]["name"] == record.name


def test_generated_description_alias_preserves_formatting_errors():
    from dataclasses import replace

    record = load_ptr_mapping(
        {"ptr_version": "0.1", "lines": [["N", 10], ["E", 10], ["S", 10]]}
    )
    with pytest.raises(ptr_core.PTRFormattingError) as error:
        ptr_core.to_technical_description(replace(record, lines=()))
    assert error.value.diagnostics[0].code == "too_few_courses"
