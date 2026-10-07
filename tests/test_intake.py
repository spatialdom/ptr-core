import json
from copy import deepcopy
from dataclasses import replace

import pytest

from ptr_core import (
    Diagnostic,
    ParcelInput,
    Severity,
    intake_candidate,
    intake_parcel,
    parse_course,
    qa_report,
    validate,
)

SQUARE = "thence North, 10 m; thence East, 10 m; thence South, 10 m; thence West, 10 m;"


def test_manual_text_and_structured_intake_share_normalization():
    text = intake_parcel(SQUARE)
    structured = intake_parcel(
        ParcelInput(
            courses=(
                {
                    "bearing": "Due North",
                    "distance": "10.00",
                    "candidate_id": "row1",
                    "sources": [{"reference": "survey-1"}],
                },
                ["East", "10"],
                parse_course("South", 10),
                ["W", 10],
            ),
            reviewed=True,
            context={"address": "Context only"},
        )
    )
    assert text.record == structured.record
    assert structured.reviewed
    assert structured.rows[0].span.candidate_id == "row1"
    assert structured.evidence["context"]["address"] == "Context only"
    assert structured.record.extra == {}


def test_partial_manual_input_keeps_invalid_row_and_optional_evidence():
    result = intake_parcel(
        ParcelInput(
            courses=(["N", 10], ["bad", 20], ["S", 10]),
            tie_point="Optional monument",
            declared_area="not numeric",
        )
    )
    assert not result.conforms
    assert [r.course is not None for r in result.rows] == [True, False, True]
    assert result.evidence["tie_point"] == "Optional monument"
    assert {"invalid_bearing", "invalid_stated_area"} <= {
        d.code for d in result.diagnostics
    }


def test_text_and_structured_disagreement_is_explicit():
    result = intake_parcel(
        ParcelInput(text=SQUARE, courses=(["N", 20], ["E", 10], ["S", 10], ["W", 10]))
    )
    assert not result.conforms
    assert "conflicting_courses" in {d.code for d in result.diagnostics}


def test_conformance_does_not_require_geometric_closure():
    result = intake_parcel("thence N, 10 m; thence E, 10 m; thence S, 5 m;")
    assert result.conforms
    report = qa_report(result.record)
    assert report.parcel.metrics.closure.linear > 0


@pytest.mark.parametrize("number", [float("inf"), float("nan"), 10**400])
def test_nonfinite_values_cannot_produce_conforming_ptr(number):
    result = validate(
        {"ptr_version": "0.1", "lines": [["N", number], ["E", 10], ["S", 10]]}
    )
    assert not result.conforms


def test_neutral_text_tie_area_and_opaque_evidence_survive_handoff():
    source = ParcelInput(
        text="Beginning at point 1, being Due West, 25 m from BLLM No. 1; " + SQUARE,
        declared_area="100",
        sources=({"uri": "opaque:survey", "custom": [1, {"anything": None}]},),
        context={"alternatives": ["Lot A", "Lot B"], "notes": {"unread": True}},
    )
    original = deepcopy(source)
    result = intake_parcel(source)
    assert result.conforms
    assert validate(result.record).conforms
    assert result.record.tie_line == parse_course("Due West", 25)
    assert result.record.tie_point == "BLLM No. 1"
    assert result.record.declared_area == 100
    assert result.record.extra == {}
    assert result.rows[1].span.sources == original.sources
    assert result.descriptions[0].tie_lines[0].span.sources == original.sources
    source.sources[0]["custom"].clear()
    source.context["alternatives"].clear()
    handoff = json.loads(json.dumps(result.to_mapping()))
    assert handoff["evidence"]["context"] == original.context
    assert handoff["evidence"]["sources"] == list(original.sources)
    handoff["evidence"]["sources"][0]["custom"].clear()
    handoff["rows"][0]["span"]["sources"][0]["custom"].clear()
    assert result.evidence["sources"][0]["custom"]
    assert result.rows[0].span.sources[0]["custom"]


@pytest.mark.parametrize("severity", [Severity.ERROR, Severity.WARNING, Severity.INFO])
def test_adapter_diagnostics_preserve_evidence_and_control_record_creation(severity):
    diagnostic = Diagnostic(
        "adapter",
        "unresolved_input",
        "Caller needs more evidence.",
        "$.context",
        severity,
    )
    source = ParcelInput(text=SQUARE, diagnostics=(diagnostic,), reviewed=True)
    result = intake_parcel(source)
    assert result.conforms == (severity is not Severity.ERROR)
    assert result.reviewed
    assert len(result.rows) == 4
    assert diagnostic in result.diagnostics
    handoff = json.loads(json.dumps(result.to_mapping()))
    assert handoff["evidence"]["diagnostics"][0]["severity"] == severity.value
    assert handoff["evidence"]["text"] == SQUARE


def test_opaque_context_is_never_used_to_decide_conformance():
    source = ParcelInput(
        text=SQUARE,
        sources=({"page_id": None, "document_id": "unresolved"},),
        context={"schema_version": "anything", "warnings": [{"code": "unknown"}]},
    )
    assert intake_parcel(source).conforms
    broken = intake_parcel(
        replace(source, text=SQUARE.replace("East, 10", "East, broken"))
    )
    assert not broken.conforms
    assert broken.rows[1].course is None
    assert broken.evidence["context"] == source.context


@pytest.mark.parametrize(
    "change",
    [
        {"tie_point": "Different monument"},
        {"tie_line": ["E", 30]},
        {"declared_area": 120},
    ],
)
def test_conflicting_text_and_explicit_metadata_are_not_erased(change):
    source = ParcelInput(
        text='Reference point: "Monument"; Stated area: 100 square metres; '
        "Beginning at point 1, being West, 25 m from Monument; " + SQUARE,
        **change,
    )
    result = intake_parcel(source)
    assert not result.conforms
    assert "conflicting_values" in {d.code for d in result.diagnostics}
    assert all(result.evidence[key] == value for key, value in change.items())


def test_tie_without_reference_blocks_intake():
    result = intake_parcel(ParcelInput(text=SQUARE, tie_line=["W", 25]))
    assert not result.conforms
    assert result.evidence["tie_line"] == ["W", 25]


def test_review_handoff_keeps_unparsed_text_tie_sources_and_row_diagnostics():
    source = ParcelInput(
        text="Beginning at point 1, being Due West, 25 m from BLLM No. 1; "
        "thence North, 10 m; thence undeciphered course; thence South, 10 m;",
        sources=({"reference": "opaque:survey-1"},),
    )
    result = intake_parcel(source)
    handoff = json.loads(json.dumps(result.to_mapping()))
    assert handoff["record"] is None
    assert handoff["rows"][1]["course"] is None
    assert handoff["rows"][1]["diagnostics"]
    description = handoff["descriptions"][0]
    assert "undeciphered" in description["unparsed_spans"][0]["text"]
    assert description["tie_lines"][0]["span"]["sources"] == list(source.sources)
    assert handoff["evidence"]["text"] == source.text


@pytest.mark.parametrize("source", [SQUARE, ParcelInput(text=SQUARE)])
def test_deprecated_intake_name_supports_neutral_input_only(source):
    with pytest.warns(DeprecationWarning, match="intake_parcel"):
        assert intake_candidate(source).record == intake_parcel(source).record


@pytest.mark.parametrize("intake", [intake_parcel, intake_candidate])
def test_external_mappings_are_rejected_with_migration_guidance(intake):
    if intake is intake_candidate:
        with pytest.warns(DeprecationWarning), pytest.raises(TypeError, match="adapt"):
            intake({"text": SQUARE})
    else:
        with pytest.raises(TypeError, match="adapt"):
            intake({"text": SQUARE})


def test_structured_invalid_row_keeps_source_and_parse_diagnostics():
    result = intake_parcel(
        ParcelInput(
            courses=(
                {"bearing": "bad", "distance": 10, "sources": "bad reference"},
                ["E", 10],
                ["S", 10],
            )
        )
    )
    assert not result.conforms
    assert {"invalid_source_reference", "invalid_bearing"} <= {
        d.code for d in result.rows[0].diagnostics
    }
