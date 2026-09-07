import pytest

from ptr_core import validate


@pytest.mark.parametrize(
    "record",
    [
        {
            "ptr_version": "0.1",
            "lines": [["N", 10.0], ["E", 10.0], ["S45-00W", 14.1421356237]],
        },
        {
            "ptr_version": "0.1",
            "name": "Lot 2173",
            "record_id": "cad-123-lot-2173",
            "tie_point": "BLLM No. 1, Cad-123",
            "tie_line": ["S11-44W", 2351.0],
            "lines": [["N", 100.0], ["E", 80.0], ["S", 100.0], ["W", 80.0]],
            "declared_area": 8000.0,
        },
        {
            "ptr_version": "0.1",
            "lines": [["N0-00-01E", 1e3], ["E", 1000], ["S45-00W", 1414.2]],
        },
    ],
)
def test_valid_records_conform(record):
    assert validate(record).conforms


@pytest.mark.parametrize(
    ("record", "code", "layer"),
    [
        ({"ptr_version": "0.1"}, "missing_lines", "structural"),
        (
            {"ptr_version": "0.1", "lines": [["N", 10.0, "extra"]]},
            "bad_course_shape",
            "structural",
        ),
        (
            {"ptr_version": "0.1", "lines": [["N", "10.0"], ["E", 1], ["S", 1]]},
            "distance_not_number",
            "structural",
        ),
        (
            {"ptr_version": "0.1", "lines": [["N", -10.0], ["E", 1], ["S", 1]]},
            "distance_not_positive",
            "semantic",
        ),
        (
            {"ptr_version": "0.1", "lines": [["N", 0], ["E", 1], ["S", 1]]},
            "distance_not_positive",
            "semantic",
        ),
        (
            {
                "ptr_version": "0.1",
                "lines": [["N", 1], ["E", 1], ["S", 1]],
                "declared_area": 0,
            },
            "declared_area_not_positive",
            "semantic",
        ),
        (
            {
                "ptr_version": "0.1",
                "tie_line": ["N", 1],
                "lines": [["N", 1], ["E", 1], ["S", 1]],
            },
            "tie_line_without_tie_point",
            "semantic",
        ),
        (
            {"ptr_version": "0.1", "lines": [["N68-60E", 1], ["E", 1], ["S", 1]]},
            "invalid_bearing",
            "semantic",
        ),
        (
            {"ptr_version": "0.1", "lines": [["N068-28E", 1], ["E", 1], ["S", 1]]},
            "invalid_bearing",
            "semantic",
        ),
    ],
)
def test_invalid_records_report_layered_diagnostics(record, code, layer):
    result = validate(record)

    assert not result.conforms
    assert any(d.code == code and d.layer == layer for d in result.errors)


def test_structured_validation_result_is_machine_readable():
    result = validate({"ptr_version": "0.1", "lines": []}).to_mapping()

    assert result["conforms"] is False
    assert result["diagnostics"][0]["severity"] == "error"

