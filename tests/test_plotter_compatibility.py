"""Semantic regressions needed by Parcel Plotter's parser removal.

Frozen documentary migration cases are shared with Extract; no application
parser or CandidateParcel contract is imported by Core.
"""

import json
from pathlib import Path

import pytest

from ptr_core import intake_parcel, parse_technical_description

CASES = json.loads(
    (Path(__file__).parent / "fixtures/migration/documentary-cases.json").read_text(
        encoding="utf-8"
    )
)["cases"]


@pytest.mark.parametrize(
    "case", [case for case in CASES if case["id"].startswith("area-")]
)
def test_documentary_area_cases(case):
    result = parse_technical_description(case["text"])
    expected = case["expected"]["areas"]
    assert [value.value for value in result.stated_areas] == [
        float(value) if value is not None else None for value in expected
    ]


def test_paste_demo_with_beginning_marker_and_numeric_word_area():
    text = (
        "Beginning at point 1; thence N45-00E, 10.00 m; thence S45-00E, 10.00 m; "
        "thence S45-00W, 10.00 m; thence N45-00W, 10.00 m; "
        "containing an area of ONE HUNDRED (100) SQUARE METRES, more or less."
    )
    result = intake_parcel(text)
    assert result.conforms
    assert result.record.declared_area == 100
    assert not result.descriptions[0].tie_lines
    assert result.rows[0].distance_text == "10.00"


def test_distance_lexeme_and_source_offsets_survive_without_rounding():
    text = "thence N45-00E, 1,810.470000000001 m;"
    row = parse_technical_description(text).rows[0]
    assert row.distance_text == "1810.470000000001"
    assert row.course.distance == 1810.470000000001
    assert text[row.span.start : row.span.end] == row.span.text
    assert row.to_mapping()["distance_text"] == row.distance_text


def test_html_whitespace_does_not_change_original_span():
    text = "thence West, 62.9 meters to the point of beginning;\u00a0&#x20;"
    row = parse_technical_description(text).rows[0]
    assert row.course.bearing.canonical == "W"
    assert row.distance_text == "62.9"
    assert text[row.span.start : row.span.end] == row.span.text


@pytest.mark.parametrize("area", ["BOGUS", "one unknown", "62.9,9", "-1", "0"])
def test_unsupported_area_is_not_repaired(area):
    result = parse_technical_description(f"containing an area of {area} square metres.")
    assert result.stated_areas[0].value is None
    assert "invalid_stated_area" in {d.code for d in result.diagnostics}
