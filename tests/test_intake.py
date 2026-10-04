import json
from copy import deepcopy
from pathlib import Path

import pytest

from ptr_core import (
    ParcelInput,
    intake_candidate,
    intake_parcel,
    parse_course,
    qa_report,
    validate,
)

FIXTURES = Path(__file__).parent / "fixtures" / "intake"
SQUARE = "thence North, 10 m; thence East, 10 m; thence South, 10 m; thence West, 10 m;"


def candidate_fixture():
    return json.loads((FIXTURES / "extract-text-v0.2.json").read_text(encoding="utf-8"))


def assembled_candidate():
    candidate = candidate_fixture()
    values = candidate["technical_description"]
    td = deepcopy(values[0])
    td["raw_text"] = "\n".join(v["raw_text"] for v in values)
    td["sources"] = [s for v in values for s in v["sources"]]
    candidate["technical_description"] = [td]
    candidate["warnings"] = []
    return candidate


def test_exact_extract_text_contract_fixture_and_provenance():
    candidate = candidate_fixture()
    original = deepcopy(candidate)
    result = intake_candidate(candidate)
    assert result.conforms
    assert validate(result.record).conforms
    assert [c.bearing.canonical for c in result.record.lines] == list("NESW")
    assert result.record.declared_area == 100
    assert result.record.tie_point == "BLLM No. 1"
    assert result.record.tie_line == parse_course("Due West", 25)
    assert result.evidence == original
    assert (
        result.rows[1].span.candidate_id
        == candidate["technical_description"][1]["candidate_id"]
    )
    assert result.rows[1].span.sources == tuple(
        candidate["technical_description"][1]["sources"]
    )
    assert result.reviewed is False
    assert candidate == original
    candidate["technical_description"][0]["sources"][0]["page_id"] = "changed"
    handoff = result.to_mapping()
    assert handoff["evidence"] == original
    handoff["evidence"]["provenance"].clear()
    assert result.evidence["provenance"]


def test_current_cross_repo_partial_conflicting_contract_fixture():
    candidate = json.loads(
        (FIXTURES / "candidate-parcel-v0.2.json").read_text(encoding="utf-8")
    )
    result = intake_candidate(candidate)
    assert not result.conforms
    assert [r.course is not None for r in result.rows] == [True, False]
    assert result.evidence == candidate
    assert {
        "uncertain_candidate",
        "multiple_candidates",
        "conflicting_stated_area",
    } <= {d.code for d in result.diagnostics}


@pytest.mark.parametrize("multi_page", [False, True])
def test_assembled_single_and_multiple_page_text(multi_page):
    candidate = assembled_candidate()
    if multi_page:
        bundle = candidate["source_bundle"]
        first = bundle["ordered_pages"][0]
        second = {**first, "page_id": "second-page", "page_index": 1}
        bundle["ordered_pages"].append(second)
        candidate["technical_description"][0]["sources"][2]["page_id"] = "second-page"
    result = intake_candidate(candidate)
    assert result.conforms
    assert result.evidence["source_bundle"] == candidate["source_bundle"]
    assert result.rows[0].span.sources == tuple(
        candidate["technical_description"][0]["sources"]
    )


@pytest.mark.parametrize(
    "field",
    [
        "stated_area",
        "reference_point",
        "tie_line",
        "technical_description",
        "parcel_identifier",
    ],
)
def test_conflicting_optional_and_required_fields_require_selection(field):
    candidate = assembled_candidate()
    if not candidate[field]:
        candidate[field] = [
            {
                **deepcopy(candidate["reference_point"][0]),
                "candidate_id": "lot",
                "raw_text": "Lot A",
            }
        ]
    value = candidate[field][0]
    alternative = {
        **deepcopy(value),
        "candidate_id": value["candidate_id"] + "-alternative",
    }
    value["status"] = alternative["status"] = "conflicting"
    value["conflict_group"] = alternative["conflict_group"] = "conflict-1"
    candidate[field].append(alternative)
    result = intake_candidate(candidate)
    assert not result.conforms
    assert len(result.evidence[field]) == 2
    assert "uncertain_candidate" in {d.code for d in result.diagnostics}


@pytest.mark.parametrize(
    "code",
    [
        "page_failed",
        "possible_missing_continuation",
        "low_quality_page",
        "unclassified_text",
    ],
)
def test_failed_page_and_continuation_warnings_prevent_record(code):
    candidate = assembled_candidate()
    candidate["warnings"] = [
        {
            "code": code,
            "message": "Retained warning",
            "candidate_ids": [],
            "sources": [],
        }
    ]
    result = intake_candidate(candidate)
    assert not result.conforms
    assert code in {d.code for d in result.diagnostics}
    assert result.evidence["warnings"] == candidate["warnings"]


def test_optional_metadata_absence_and_uncertain_address_allow_local_ptr():
    candidate = assembled_candidate()
    for name in ("reference_point", "tie_line", "stated_area", "parcel_identifier"):
        candidate[name] = []
    candidate["address_locality"] = [
        {
            **deepcopy(candidate["technical_description"][0]),
            "candidate_id": "address",
            "raw_text": "Uncertain locality",
            "status": "ambiguous",
        }
    ]
    result = intake_candidate(candidate)
    assert result.conforms
    assert result.record.tie_point is None
    assert result.record.extra == {}
    assert result.evidence["address_locality"] == candidate["address_locality"]


def test_disagreeing_tie_reference_and_explicit_reference_are_not_erased():
    candidate = assembled_candidate()
    candidate["reference_point"][0]["raw_text"] = "Different monument"
    result = intake_candidate(candidate)
    assert not result.conforms
    assert "conflicting_values" in {d.code for d in result.diagnostics}


def test_no_selection_of_overlapping_or_reordered_description_spans():
    candidate = candidate_fixture()
    candidate["technical_description"].reverse()
    result = intake_candidate(candidate)
    assert not result.conforms
    assert "multiple_candidates" in {d.code for d in result.diagnostics}


def test_high_ocr_confidence_does_not_override_malformed_course():
    candidate = assembled_candidate()
    td = candidate["technical_description"][0]
    td["confidence"] = 1.0
    td["raw_text"] = td["raw_text"].replace("East, 10.0", "East, broken")
    result = intake_candidate(candidate)
    assert not result.conforms
    assert result.rows[1].course is None
    assert result.evidence["technical_description"][0]["confidence"] == 1.0


def test_candidate_to_dict_protocol_without_extractor_import():
    class NeutralCandidate:
        def to_dict(self):
            return assembled_candidate()

    assert intake_candidate(NeutralCandidate()).conforms


def test_manual_text_and_structured_intake_share_normalization():
    text = intake_parcel(SQUARE)
    structured = intake_parcel(
        ParcelInput(
            courses=(
                {
                    "bearing": "Due North",
                    "distance": "10.00",
                    "candidate_id": "row1",
                    "sources": [{"page_id": "p1"}],
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


@pytest.mark.parametrize("field", ["stated_area", "reference_point", "tie_line"])
def test_missing_optional_extraction_warnings_allow_local_record(field):
    candidate = assembled_candidate()
    candidate[field] = []
    if field == "reference_point":
        candidate["tie_line"] = []
    candidate["warnings"] = [
        {"code": "missing_" + field, "message": "Missing optional metadata"}
    ]
    assert intake_candidate(candidate).conforms


@pytest.mark.parametrize(
    "change,code",
    [
        ({"schema_version": "0.1"}, "unsupported_candidate_version"),
        ({"source_bundle": None}, "invalid_source_bundle"),
        ({"warnings": None}, "invalid_candidate_field"),
        ({"provenance": None}, "invalid_candidate_field"),
        ({"failed_page_ids": ["unread-page"]}, "failed_pages"),
    ],
)
def test_invalid_or_failed_contract_is_retained(change, code):
    candidate = assembled_candidate()
    candidate.update(change)
    result = intake_candidate(candidate)
    assert not result.conforms
    assert code in {d.code for d in result.diagnostics}
    assert result.evidence == candidate


def test_unresolved_provenance_and_sources_are_explicit():
    candidate = assembled_candidate()
    td = candidate["technical_description"][0]
    td["extraction_id"] = "missing-run"
    td["sources"][0]["page_id"] = "missing-page"
    result = intake_candidate(candidate)
    assert not result.conforms
    assert {"invalid_provenance", "invalid_source_reference"} <= {
        d.code for d in result.diagnostics
    }


def test_review_handoff_keeps_unparsed_text_tie_sources_and_row_diagnostics():
    candidate = assembled_candidate()
    td = candidate["technical_description"][0]
    td["raw_text"] = (
        "Beginning at point 1, being Due West, 25 m from BLLM No. 1; "
        "thence North, 10 m; thence undeciphered course; "
        "thence South, 10 m;"
    )
    result = intake_candidate(candidate)
    handoff = json.loads(json.dumps(result.to_mapping()))
    assert handoff["record"] is None
    assert handoff["rows"][1]["course"] is None
    assert handoff["rows"][1]["diagnostics"]
    description = handoff["descriptions"][0]
    assert "undeciphered" in description["unparsed_spans"][0]["text"]
    assert description["tie_lines"][0]["span"]["candidate_id"] == td["candidate_id"]
    assert handoff["evidence"] == candidate
