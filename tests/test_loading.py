from pathlib import Path

import pytest

from ptr_core import PTRParseError, dumps_ptr, load_ptr, load_ptr_mapping, validate

MINIMAL_PTR = """{
  "ptr_version": "0.1",
  "lines": [
    ["N", 10.0],
    ["E", 10.0],
    ["S45-00W", 14.1421356237]
  ]
}
"""


COMPLETE_MAPPING = {
    "ptr_version": "0.1",
    "name": "Lot 2173",
    "record_id": "cad-123-lot-2173",
    "tie_point": "BLLM No. 1, Cad-123",
    "tie_line": ["S11-44W", 2351.0],
    "lines": [["N", 100.0], ["E", 80.0], ["S", 100.0], ["W", 80.0]],
    "declared_area": 8000.0,
}


def test_loads_ptr_from_text_mapping_and_path(tmp_path: Path):
    path = tmp_path / "minimal.ptr"
    path.write_text(MINIMAL_PTR, encoding="utf-8")

    assert load_ptr(MINIMAL_PTR).lines[2].bearing.canonical == "S45-00W"
    assert load_ptr(path).lines[0].distance == 10.0
    assert load_ptr_mapping(COMPLETE_MAPPING).tie_line is not None


def test_loaded_record_is_immutable_and_preserves_line_order():
    record = load_ptr_mapping(COMPLETE_MAPPING)

    assert [course.bearing.canonical for course in record.lines] == ["N", "E", "S", "W"]
    with pytest.raises(AttributeError):
        record.name = "changed"  # type: ignore[misc]


def test_serializes_to_canonical_json():
    record = load_ptr_mapping(
        {
            "ptr_version": "0.1",
            "lines": [["n", 1], [" e ", 1], ["S45-00W", 1.4142]],
        },
        normalize_bearings=True,
    )

    assert dumps_ptr(record) == (
        '{"ptr_version":"0.1","lines":[["N",1.0],["E",1.0],'
        '["S45-00W",1.4142]]}\n'
    )


def test_load_rejects_nonconforming_record():
    with pytest.raises(PTRParseError):
        load_ptr('{"ptr_version":"0.1","lines":[["N68-60E", 10.0]]}')


def test_validate_text_reports_serialization_error():
    result = validate('{"ptr_version": "0.1", "lines": [')

    assert not result.conforms
    assert result.errors[0].layer == "serialization"
