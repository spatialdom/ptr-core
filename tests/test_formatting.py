from dataclasses import replace

import pytest

from ptr_core import (
    Course,
    ParcelInput,
    PTRFormattingError,
    format_technical_description,
    intake_parcel,
    load_ptr_mapping,
    parse_bearing,
    parse_technical_description,
    project_manual_table,
)


def record_fixture():
    return load_ptr_mapping(
        {
            "ptr_version": "0.1",
            "name": "Synthetic parcel",
            "record_id": "record-1",
            "lines": [
                ["N", 10.123456789012345],
                ["N45-30-12E", 12.000000000000002],
                ["S45-30W", 15.765432109876543],
                ["W", 2.2250738585072014e-308],
            ],
            "tie_point": (
                'BLLM No. 1; "thence" North / continuation (synthetic)\nsecond line'
            ),
            "tie_line": ["E", 123456789.12345679],
            "declared_area": 12.123456789012345,
            "extension": {"opaque": [None, "value", 2.0]},
        }
    )


def test_generated_prose_round_trip_preserves_supported_semantics():
    record = record_fixture()
    generated = format_technical_description(record)
    parsed = parse_technical_description(generated.text)
    assert parsed.complete
    assert parsed.courses == record.lines
    assert parsed.tie_lines[0].course == record.tie_line
    assert parsed.reference_points[0].value == record.tie_point
    assert parsed.stated_areas[0].value == record.declared_area
    result = intake_parcel(generated.text)
    assert result.conforms
    assert result.record == replace(record, name=None, record_id=None, extra={})
    assert generated.omitted_fields == ("name", "record_id", "extra.extension")
    assert generated.diagnostics[0].code == "metadata_not_in_prose"
    assert not any(r.returns_to_beginning for r in parsed.rows)


@pytest.mark.parametrize(
    "reference",
    [
        None,
        "",
        " ",
        "Monument; thence West",
        'Quote "inside" reference',
        "Monument 😀\ncontinued on next page",
    ],
)
@pytest.mark.parametrize("with_tie", [False, True])
def test_reference_round_trip_with_reserved_punctuation(reference, with_tie):
    if reference is None and with_tie:
        return
    data = {"ptr_version": "0.1", "lines": [["N", 10], ["E", 10], ["S", 10]]}
    if reference is not None:
        data["tie_point"] = reference
    if with_tie:
        data["tie_line"] = ["W", 25]
    record = load_ptr_mapping(data)
    generated = format_technical_description(record)
    result = intake_parcel(generated.text)
    assert result.conforms
    assert result.record == record


def test_manual_table_projection_is_lossless_and_metadata_is_separate():
    record = record_fixture()
    projection = project_manual_table(record)
    table = projection.to_mapping()
    assert [row["bearing"] for row in table["rows"]] == [
        c.bearing.canonical for c in record.lines
    ]
    assert [row["distance"] for row in table["rows"]] == [
        c.distance for c in record.lines
    ]
    assert table["metadata"]["tie_point"] == record.tie_point
    assert table["metadata"]["tie_line"] == record.tie_line.to_json_value()
    assert "lines" not in table["metadata"]
    assert table["extensions"] == record.extra
    assert load_ptr_mapping(projection.to_ptr_mapping()) == record
    table["extensions"]["extension"]["opaque"].clear()
    assert record.extra["extension"]["opaque"]
    assert projection.extensions["extension"]["opaque"]
    manual = intake_parcel(ParcelInput(courses=tuple(projection.to_mapping()["rows"])))
    assert manual.record.lines == record.lines


def test_formatter_does_not_compute_geometry_or_assert_closure(monkeypatch):
    import ptr_core.geometry

    def unexpected(*args, **kwargs):
        raise AssertionError("Formatting must not reconstruct geometry")

    monkeypatch.setattr(ptr_core.geometry, "reconstruct", unexpected)
    record = load_ptr_mapping(
        {"ptr_version": "0.1", "lines": [["N", 10], ["E", 10], ["S", 1]]}
    )
    generated = format_technical_description(record)
    assert "point of beginning" not in generated.text.lower()
    assert "certified" not in generated.text.lower()
    assert "Generated technical description." in generated.text
    assert project_manual_table(record).rows


@pytest.mark.parametrize(
    "change",
    [
        {"lines": ()},
        {"ptr_version": "0.2"},
        {"declared_area": float("nan")},
        {"tie_point": None, "tie_line": Course(parse_bearing("N"), 10)},
        {"lines": (Course(parse_bearing("N"), -1),) * 3},
        {"extra": {"lines": [["N", 10], ["E", 10], ["S", 10]]}},
        {"extra": {"unserializable": object()}},
    ],
)
@pytest.mark.parametrize(
    "formatter", [format_technical_description, project_manual_table]
)
def test_invalid_records_fail_with_explicit_diagnostics(change, formatter):
    with pytest.raises(PTRFormattingError) as error:
        formatter(replace(record_fixture(), **change))
    assert error.value.diagnostics


def test_neutral_intake_generated_description_intake_round_trip():
    source = ParcelInput(
        text="Beginning at point 1, being Due West, 25 m from BLLM No. 1; "
        "thence North, 10 m; thence East, 10 m; thence South, 10 m; thence West, 10 m;",
        declared_area=100,
        sources=({"reference": "opaque:survey"},),
    )
    original = intake_parcel(source)
    generated = format_technical_description(original.record)
    round_trip = intake_parcel(generated.text)
    assert round_trip.record == original.record
    assert original.evidence["sources"] == list(source.sources)
