from pathlib import Path

import pytest

from ptr_core import PTRParseError, load_ptr, parse_bearing, qa_report, validate

CORPUS = Path(__file__).parent / "conformance" / "ptr-v0.1"
PROVENANCE_COMMIT = "0e5169d7c72cf7d14106eae850b8cb7f44f2da3e"

VALID_FIXTURES = [
    "examples/minimal/minimal.ptr",
    "examples/complete/complete.ptr",
    "tests/valid/cardinal-square.ptr",
    "tests/valid/quadrant-triangle.ptr",
    "tests/valid/scientific-distance.ptr",
    "tests/bearings/bearing-seconds.ptr",
    "tests/tie_points/tie-line.ptr",
    "tests/edge_cases/minimum-offset-seconds.ptr",
]

INVALID_FIXTURES = {
    "tests/invalid/invalid-json.ptr": "serialization",
    "tests/invalid/missing-lines.ptr": "structural",
    "tests/invalid/bad-course-shape.ptr": "structural",
    "tests/invalid/negative-distance.ptr": "semantic",
    "tests/invalid/zero-distance.ptr": "semantic",
    "tests/invalid/string-distance.ptr": "structural",
    "tests/invalid/zero-declared-area.ptr": "semantic",
    "tests/invalid/tie-line-without-tie-point.ptr": "semantic",
    "tests/bearings/invalid-bearing-minutes.ptr": "semantic",
    "tests/bearings/invalid-bearing-leading-zero.ptr": "semantic",
    "tests/bearings/invalid-bearing-zero-seconds.ptr": "semantic",
    "tests/ambiguous/ambiguous-bearing-stored.ptr": "semantic",
}

QA_FIXTURES = {
    "tests/closure/non-closing.ptr": {"misclosure"},
    "tests/closure/counterclockwise-order.ptr": {"counterclockwise_orientation"},
    "tests/closure/self-intersecting.ptr": {"self_intersection"},
}


def test_conformance_fixture_provenance_is_visible():
    provenance = (CORPUS / "PROVENANCE.md").read_text(encoding="utf-8")

    assert PROVENANCE_COMMIT in provenance


@pytest.mark.parametrize("fixture", VALID_FIXTURES)
def test_valid_conformance_fixtures_parse_and_validate(fixture):
    path = CORPUS / fixture

    assert validate(path.read_text(encoding="utf-8")).conforms
    assert load_ptr(path).ptr_version == "0.1"


@pytest.mark.parametrize(("fixture", "expected_layer"), INVALID_FIXTURES.items())
def test_invalid_conformance_fixtures_fail_expected_layer(fixture, expected_layer):
    path = CORPUS / fixture
    result = validate(path.read_text(encoding="utf-8"))

    assert not result.conforms
    assert result.errors[0].layer == expected_layer
    with pytest.raises(PTRParseError):
        load_ptr(path)


def test_ambiguous_bearing_input_fixture_is_rejected():
    value = (CORPUS / "tests/ambiguous/ambiguous-bearing-input.txt").read_text(
        encoding="utf-8"
    )

    with pytest.raises(ValueError):
        parse_bearing(value)


@pytest.mark.parametrize(("fixture", "expected_codes"), QA_FIXTURES.items())
def test_geometric_qa_conformance_fixtures_report_expected_findings(
    fixture, expected_codes
):
    path = CORPUS / fixture
    report = qa_report(path)
    codes = {finding.code for finding in report.diagnostics}

    assert report.conforms
    assert expected_codes <= codes
