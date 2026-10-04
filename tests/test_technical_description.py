import json
from pathlib import Path

import pytest

from ptr_core import (
    CourseParseError,
    parse_course,
    parse_distance,
    parse_technical_description,
)

FIXTURES = Path(__file__).parent / "fixtures" / "migration"
CASES = {
    c["id"]: c
    for c in json.loads(
        (FIXTURES / "documentary-cases.json").read_text(encoding="utf-8")
    )["cases"]
}
OBSERVATIONS = json.loads(
    (FIXTURES / "legacy-observations.json").read_text(encoding="utf-8")
)["observations"]


@pytest.mark.parametrize(
    "case_id",
    [
        "quadrant-punctuation",
        "cardinal-directions",
        "degree-prime-curly-quotes",
        "tie-bllm",
        "tie-pbm",
        "tie-triangulation",
        "tie-fire-hydrant",
        "tie-cardinal",
    ],
)
def test_migrated_course_and_tie_semantics_against_frozen_legacy(case_id):
    text = CASES[case_id]["text"]
    result = parse_technical_description(text)
    legacy = OBSERVATIONS[case_id]
    assert len(result.courses) == len(legacy["courses"])
    for row, expected in zip(result.rows, legacy["courses"], strict=True):
        bearing = expected.get("cardinal") or (
            f"{expected['north_south']}{expected['degrees']}-"
            f"{expected['minutes']:02d}{expected['east_west']}"
        )
        assert row.course == parse_course(bearing, expected["distance_m"])
        assert row.destination_point == expected["destination_point"]
        assert row.returns_to_beginning == expected["returns_to_beginning"]
        assert text[row.span.start : row.span.end] == row.span.text
    tie = legacy["tie_line_candidate"]
    if tie:
        assert len(result.tie_lines) == 1
        assert result.tie_lines[0].course.distance == float(tie["distance_m"])
        assert result.tie_lines[0].reference_point == tie["reference_text"]
    assert not any(row.diagnostics for row in (*result.rows, *result.tie_lines))


@pytest.mark.parametrize(
    "case_id",
    [
        "invalid-degrees",
        "invalid-minutes",
        "missing-bearing-minutes",
        "missing-distance",
        "corrupted-distance",
    ],
)
def test_malformed_legacy_course_is_retained(case_id):
    text = CASES[case_id]["text"]
    result = parse_technical_description(text)
    assert len(result.rows) == 1
    assert result.rows[0].course is None
    assert result.rows[0].diagnostics
    assert (
        text[result.rows[0].span.start : result.rows[0].span.end]
        == result.rows[0].span.text
    )
    assert not result.complete


@pytest.mark.parametrize("case_id", ["tie-invalid-range", "tie-ocr-anchor", "tie-bbm"])
def test_no_ocr_or_leading_zero_bearing_repair(case_id):
    result = parse_technical_description(CASES[case_id]["text"])
    assert len(result.tie_lines) == 1
    assert result.tie_lines[0].course is None
    assert result.tie_lines[0].diagnostics


def test_partial_course_order_and_source_links_survive():
    text = CASES["partial-unparsed-thence"]["text"]
    links = [{"document_id": "d1", "page_id": "p1"}]
    result = parse_technical_description(text, candidate_id="td1", sources=links)
    links[0]["page_id"] = "modified"
    assert [r.course is not None for r in result.rows] == [True, False, True]
    assert result.rows[1].span.candidate_id == "td1"
    assert result.rows[1].span.sources[0]["page_id"] == "p1"
    assert not result.complete


def test_manual_rows_seconds_and_wrapped_thence_share_course_parser():
    result = parse_technical_description(
        "Due North, 10 m\nN45-30-12E 12.345678901234 m\nWest 10 m"
    )
    assert result.complete
    assert result.courses[1] == parse_course("N45-30-12E", "12.345678901234")
    wrapped = parse_technical_description(
        "thence Due\nNorth,\n10 m; thence East, 10 m; thence South, 10 m;"
    )
    assert wrapped.complete
    assert wrapped.courses[0].bearing.canonical == "N"


@pytest.mark.parametrize(
    "value",
    [0, -1, True, float("nan"), float("inf"), "1,00", "62.9,9", "10ft", "1e999"],
)
def test_invalid_distance_is_deterministic(value):
    with pytest.raises(CourseParseError) as error:
        parse_distance(value)
    assert error.value.code == "invalid_distance"


@pytest.mark.parametrize(
    "value,expected", [("1,810.47", 1810.47), ("1e-3", 0.001), (" 10.00 ", 10)]
)
def test_numeric_distance_normalization(value, expected):
    assert parse_distance(value) == expected


def test_destination_and_return_are_documentary_only():
    result = parse_technical_description(
        "thence N, 10 m to point 2; thence E, 10 m; thence S, 10 m;"
    )
    assert result.complete
    assert result.rows[0].destination_point == 2
    assert not any(row.returns_to_beginning for row in result.rows)
    continuation = parse_technical_description(
        "thence N, 10 m; thence E, 10 m; thence S, 10 m; continued on next page"
    )
    assert not continuation.complete
    assert "unresolved_continuation" in {d.code for d in continuation.diagnostics}


def test_optional_values_do_not_choose_conflicting_alternatives():
    result = parse_technical_description(
        'Reference point: "Monument A"; Reference point: "Monument B"; '
        'Stated area: 100 square metres; Stated area: 120 square metres;'
    )
    assert [v.value for v in result.reference_points] == ["Monument A", "Monument B"]
    assert [v.value for v in result.stated_areas] == [100, 120]
