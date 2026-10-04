"""Library-neutral candidate intake; documentary evidence stays outside PTR."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Protocol

from ptr_core.io import load_ptr_mapping
from ptr_core.models import Course, PTRRecord
from ptr_core.technical_description import (
    CourseParseError,
    ParsedCourse,
    SourceSpan,
    TechnicalDescriptionResult,
    parse_course,
    parse_distance,
    parse_technical_description,
)
from ptr_core.validation import Diagnostic, Severity, validate_mapping


class CandidateMapping(Protocol):
    """Structural compatibility with CandidateParcel.to_dict(), without imports."""

    def to_dict(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class ParcelInput:
    """Explicit application/manual input; not an extraction schema or PTR."""

    text: str | None = None
    courses: tuple[object, ...] | None = None
    tie_point: str | None = None
    tie_line: object = None
    declared_area: object = None
    name: str | None = None
    record_id: str | None = None
    reviewed: bool = False
    sources: tuple[Mapping[str, Any], ...] = ()
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IntakeResult:
    record: PTRRecord | None
    rows: tuple[ParsedCourse, ...]
    descriptions: tuple[TechnicalDescriptionResult, ...]
    diagnostics: tuple[Diagnostic, ...]
    evidence: Mapping[str, Any]
    reviewed: bool = False

    @property
    def conforms(self) -> bool:
        return self.record is not None

    def to_mapping(self) -> dict[str, Any]:
        """Review handoff, including source evidence; never log automatically."""
        return {
            "record": self.record.to_mapping() if self.record else None,
            "reviewed": self.reviewed,
            "diagnostics": [
                {
                    "layer": d.layer,
                    "code": d.code,
                    "message": d.message,
                    "path": d.path,
                    "severity": d.severity.value,
                }
                for d in self.diagnostics
            ],
            "rows": [row.to_mapping() for row in self.rows],
            "descriptions": [
                description.to_mapping() for description in self.descriptions
            ],
            "evidence": deepcopy(dict(self.evidence)),
        }


def _error(code: str, message: str, path: str = "$") -> Diagnostic:
    return Diagnostic("intake", code, message, path)


def _unique(
    values: Sequence[Any], field_name: str, diagnostics: list[Diagnostic]
) -> Any:
    present = [v for v in values if v is not None]
    if not present:
        return None
    if any(value != present[0] for value in present[1:]):
        diagnostics.append(
            _error(
                "conflicting_values",
                f"Conflicting {field_name} values require selection.",
                f"$.{field_name}",
            )
        )
        return None
    return present[0]


def _structured_row(
    value: object, index: int, sources: Sequence[Mapping[str, Any]]
) -> ParsedCourse:
    candidate_id = None
    raw = repr(value)
    errors: list[Diagnostic] = []
    if isinstance(value, Mapping):
        candidate_id = value.get("candidate_id")
        raw_value = value.get("raw_text")
        raw = raw_value if isinstance(raw_value, str) else repr(dict(value))
        links = value.get("sources", sources)
        bearing = value.get("bearing")
        distance = value.get("distance", value.get("distance_m"))
    else:
        links = sources
        bearing, distance = (
            value
            if isinstance(value, list | tuple) and len(value) == 2
            else (None, None)
        )
    if not isinstance(links, list | tuple) or any(
        not isinstance(s, Mapping) for s in links
    ):
        errors.append(
            _error(
                "invalid_source_reference",
                "Row sources must be mappings.",
                f"$.courses[{index}]",
            )
        )
        links = ()
    span = SourceSpan(
        0, len(raw), raw, candidate_id, tuple(deepcopy(dict(s)) for s in links)
    )
    try:
        if isinstance(value, Course):
            course = parse_course(value.bearing.canonical, value.distance)
        else:
            if not isinstance(bearing, str):
                raise CourseParseError(
                    "Course bearing must be a string.", code="invalid_bearing"
                )
            course = parse_course(bearing, distance)
        destination = (
            value.get("destination_point") if isinstance(value, Mapping) else None
        )
        returns = (
            value.get("returns_to_beginning", False)
            if isinstance(value, Mapping)
            else False
        )
        if destination is not None and (
            type(destination) is not int or destination < 1
        ):
            errors.append(
                _error(
                    "invalid_destination",
                    "Point labels must be positive integers.",
                    f"$.courses[{index}]",
                )
            )
            destination = None
        if not isinstance(returns, bool):
            errors.append(
                _error(
                    "invalid_destination",
                    "Return indicator must be boolean.",
                    f"$.courses[{index}]",
                )
            )
            returns = False
        return ParsedCourse(
            course, span, destination, returns, diagnostics=tuple(errors)
        )
    except CourseParseError as exc:
        return ParsedCourse(
            None, span, diagnostics=(_error(exc.code, str(exc), f"$.courses[{index}]"),)
        )


def _tie_course(
    value: object, diagnostics: list[Diagnostic]
) -> tuple[Course | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, str):
        parsed = parse_technical_description(value)
        diagnostics.extend(d for d in parsed.diagnostics if d.code != "too_few_courses")
        rows = (*parsed.rows, *parsed.tie_lines)
        if len(rows) != 1:
            diagnostics.append(
                _error(
                    "invalid_tie_line",
                    "Expected exactly one tie-line course.",
                    "$.tie_line",
                )
            )
            return None, None
        return rows[0].course, rows[0].reference_point
    row = _structured_row(value, 0, ())
    diagnostics.extend(row.diagnostics)
    return row.course, None


def _finish(
    data: dict[str, Any],
    rows: Sequence[ParsedCourse],
    descriptions: Sequence[TechnicalDescriptionResult],
    diagnostics: list[Diagnostic],
    evidence: Mapping[str, Any],
    reviewed: bool = False,
) -> IntakeResult:
    data["ptr_version"] = "0.1"
    data["lines"] = [row.course.to_json_value() for row in rows if row.course]
    diagnostics.extend(validate_mapping(data).diagnostics)
    record = None
    if not any(d.severity is Severity.ERROR for d in diagnostics):
        record = load_ptr_mapping(data)
    return IntakeResult(
        record,
        tuple(rows),
        tuple(descriptions),
        tuple(diagnostics),
        deepcopy(dict(evidence)),
        reviewed,
    )


def intake_parcel(source: str | ParcelInput) -> IntakeResult:
    """Intake manual/pasted text or explicitly supplied structured courses."""
    if isinstance(source, str):
        source = ParcelInput(text=source)
    diagnostics: list[Diagnostic] = []
    descriptions: list[TechnicalDescriptionResult] = []
    rows: list[ParsedCourse] = []
    references: list[object] = [source.tie_point]
    areas: list[object] = []
    ties: list[Course | None] = []
    if source.text is not None:
        parsed = parse_technical_description(source.text, sources=source.sources)
        descriptions.append(parsed)
        rows.extend(parsed.rows)
        diagnostics.extend(parsed.diagnostics)
        references.extend(v.value for v in parsed.reference_points)
        areas.extend(v.value for v in parsed.stated_areas)
        ties.extend(row.course for row in parsed.tie_lines)
    if source.courses is not None:
        structured = [
            _structured_row(v, i, source.sources) for i, v in enumerate(source.courses)
        ]
        diagnostics.extend(d for row in structured for d in row.diagnostics)
        if source.text is not None:
            if [r.course for r in structured] != [r.course for r in rows]:
                diagnostics.append(
                    _error(
                        "conflicting_courses", "Text and structured courses disagree."
                    )
                )
            # Retain both representations in evidence; text rows carry spans.
        else:
            rows = structured
    if source.declared_area is not None:
        try:
            areas.append(parse_distance(source.declared_area))
        except CourseParseError as exc:
            diagnostics.append(
                _error("invalid_stated_area", str(exc), "$.declared_area")
            )
    tie, reference = _tie_course(source.tie_line, diagnostics)
    ties.append(tie)
    references.append(reference)
    data: dict[str, Any] = {}
    for key, value in (
        ("name", source.name),
        ("record_id", source.record_id),
        ("tie_point", _unique(references, "tie_point", diagnostics)),
        ("declared_area", _unique(areas, "declared_area", diagnostics)),
    ):
        if value is not None:
            data[key] = value
    selected_tie = _unique(ties, "tie_line", diagnostics)
    if selected_tie:
        data["tie_line"] = selected_tie.to_json_value()
    evidence = {
        "text": source.text,
        "courses": [
            v.to_json_value() if isinstance(v, Course) else v for v in source.courses
        ]
        if source.courses is not None
        else None,
        "tie_point": source.tie_point,
        "tie_line": source.tie_line.to_json_value()
        if isinstance(source.tie_line, Course)
        else source.tie_line,
        "declared_area": source.declared_area,
        "name": source.name,
        "record_id": source.record_id,
        "sources": list(source.sources),
        "context": dict(source.context),
        "reviewed": source.reviewed,
    }
    return _finish(data, rows, descriptions, diagnostics, evidence, source.reviewed)


_FIELDS = (
    "parcel_identifier",
    "stated_area",
    "address_locality",
    "reference_point",
    "tie_line",
    "technical_description",
)
_INFORMATIONAL = {
    "parcel_semantics_unchecked",
    "missing_stated_area",
    "missing_reference_point",
    "missing_tie_line",
    "multiple_address_locality_candidates",
}
_METRIC_AREA = re.compile(r"square\s+(?:meters?|metres?)|sq\.?\s*m\.?|sqm|m2", re.I)


def _ordered_fragments(
    values: Sequence[Mapping[str, Any]], pages: Mapping[Any, Any]
) -> bool:
    """Recognize Extract's disjoint thence spans; never infer page assembly."""
    if len(values) < 2:
        return False
    page_order = {pid: i for i, pid in enumerate(pages)}
    previous: tuple[int, int] | None = None
    for value in values:
        text = value.get("raw_text", "")
        if not isinstance(text, str) or not re.match(r"\s*thence\b", text, re.I):
            return False
        if len(re.findall(r"\bthence\b", text, re.I)) != 1:
            return False
        links = value.get("sources")
        if (
            not isinstance(links, list | tuple)
            or len(links) != 1
            or not isinstance(links[0], Mapping)
        ):
            return False
        link = links[0]
        span = link.get("text_span")
        page = page_order.get(link.get("page_id"))
        if page is None or not isinstance(span, Mapping):
            return False
        start, end = span.get("start"), span.get("end")
        if type(start) is not int or type(end) is not int or start < 0 or end <= start:
            return False
        if previous is not None and (page, start) < previous:
            return False
        previous = (page, end)
    return True


def _candidate_shape(evidence: Mapping[str, Any]) -> tuple[Diagnostic, ...]:
    """Validate transport shape before following opaque references."""
    errors: list[Diagnostic] = []
    bundle = evidence.get("source_bundle")
    if not isinstance(bundle, Mapping):
        return (_error("invalid_source_bundle", "source_bundle must be a mapping."),)
    for key in ("documents", "ordered_pages"):
        values = bundle.get(key)
        if (
            not isinstance(values, list | tuple)
            or not values
            or any(not isinstance(v, Mapping) for v in values)
        ):
            errors.append(
                _error(
                    "invalid_source_bundle", f"{key} must be a nonempty mapping array."
                )
            )
    for key in (*_FIELDS, "provenance", "warnings"):
        values = evidence.get(key, [])
        if not isinstance(values, list | tuple) or any(
            not isinstance(v, Mapping) for v in values
        ):
            errors.append(
                _error(
                    "invalid_candidate_field",
                    "Field must be a mapping array.",
                    f"$.{key}",
                )
            )
    if errors:
        return tuple(errors)
    for warning in evidence.get("warnings", []):
        if isinstance(warning, Mapping) and not isinstance(warning.get("code"), str):
            errors.append(
                _error("invalid_extraction_warning", "Warning code must be a string.")
            )
    if errors:
        return tuple(errors)
    documents = bundle["documents"]
    doc_ids = [v.get("document_id") for v in documents]
    pages = bundle["ordered_pages"]
    page_ids = [v.get("page_id") for v in pages]
    extraction_ids = [v.get("extraction_id") for v in evidence.get("provenance", [])]
    for ids in (doc_ids, page_ids, extraction_ids):
        if any(not isinstance(v, str) or not v.strip() for v in ids) or len(
            set(ids)
        ) != len(ids):
            errors.append(
                _error(
                    "invalid_source_bundle",
                    "Source and extraction IDs must be unique nonblank strings.",
                )
            )
            return tuple(errors)
    for page in pages:
        if (
            page.get("document_id") not in doc_ids
            or type(page.get("page_index")) is not int
            or page["page_index"] < 0
        ):
            errors.append(
                _error(
                    "invalid_source_bundle",
                    "Page must resolve to a document and nonnegative index.",
                )
            )
    for name in _FIELDS:
        for value in evidence.get(name, []):
            links = value.get("sources")
            if (
                not isinstance(links, list | tuple)
                or not links
                or any(
                    not isinstance(s, Mapping)
                    or not isinstance(s.get("page_id"), str)
                    or not isinstance(s.get("document_id"), str)
                    for s in links
                )
            ):
                errors.append(
                    _error(
                        "invalid_source_reference",
                        "Candidate sources must be nonempty source mappings.",
                        f"$.{name}",
                    )
                )
            if not isinstance(value.get("extraction_id"), str):
                errors.append(
                    _error(
                        "invalid_provenance",
                        "Extraction ID must be a string.",
                        f"$.{name}",
                    )
                )
    return tuple(errors)


def intake_candidate(candidate: Mapping[str, Any] | CandidateMapping) -> IntakeResult:
    """Consume CandidateParcel 0.2 evidence without importing PTR Extract.

    Competing candidates require downstream selection, including optional PTR
    fields. One description must already be assembled by the caller. Confidence
    remains evidence and has no influence on parcel conformance.
    """
    evidence = deepcopy(
        dict(candidate if isinstance(candidate, Mapping) else candidate.to_dict())
    )
    diagnostics: list[Diagnostic] = []
    descriptions: list[TechnicalDescriptionResult] = []
    rows: list[ParsedCourse] = []
    data: dict[str, Any] = {}
    shape_errors = _candidate_shape(evidence)
    if shape_errors:
        return _finish(data, rows, descriptions, list(shape_errors), evidence)
    if evidence.get("schema_version") != "0.2":
        diagnostics.append(
            _error(
                "unsupported_candidate_version",
                "CandidateParcel schema_version must be 0.2.",
            )
        )
    bundle = evidence.get("source_bundle")
    pages: dict[Any, Any] = {}
    if isinstance(bundle, Mapping):
        for page in bundle.get("ordered_pages", []):
            if isinstance(page, Mapping):
                pages[page.get("page_id")] = page.get("document_id")
    if not pages:
        diagnostics.append(
            _error("invalid_source_bundle", "Candidate source pages are required.")
        )
    provenance = {
        p.get("extraction_id")
        for p in evidence.get("provenance", [])
        if isinstance(p, Mapping)
    }
    ids: set[str] = set()
    active: dict[str, list[Mapping[str, Any]]] = {}
    for name in _FIELDS:
        values = evidence.get(name, [])
        active[name] = []
        if not isinstance(values, list | tuple):
            diagnostics.append(
                _error(
                    "invalid_candidate_field",
                    "Candidate fields must be arrays.",
                    f"$.{name}",
                )
            )
            continue
        for index, value in enumerate(values):
            path = f"$.{name}[{index}]"
            if not isinstance(value, Mapping):
                diagnostics.append(
                    _error("invalid_candidate", "Candidate must be a mapping.", path)
                )
                continue
            cid = value.get("candidate_id")
            if not isinstance(cid, str) or not cid or cid in ids:
                diagnostics.append(
                    _error(
                        "invalid_candidate_id",
                        "Candidate IDs must be unique nonblank strings.",
                        path,
                    )
                )
            else:
                ids.add(cid)
            links = value.get("sources")
            if (
                not isinstance(links, list | tuple)
                or not links
                or any(
                    not isinstance(s, Mapping)
                    or s.get("page_id") not in pages
                    or pages.get(s.get("page_id")) != s.get("document_id")
                    for s in (links or [])
                )
            ):
                diagnostics.append(
                    _error(
                        "invalid_source_reference",
                        "Candidate source must resolve to a bundled page.",
                        path,
                    )
                )
            if value.get("extraction_id") not in provenance:
                diagnostics.append(
                    _error(
                        "invalid_provenance",
                        "Candidate extraction ID must resolve.",
                        path,
                    )
                )
            status = value.get("status")
            if status not in ("found", "ambiguous", "conflicting", "not_found"):
                diagnostics.append(
                    _error(
                        "invalid_candidate_status", "Unknown extraction status.", path
                    )
                )
            if status == "not_found":
                if any(
                    value.get(k) is not None
                    for k in ("raw_text", "document_text", "documentary_number")
                ):
                    diagnostics.append(
                        _error(
                            "invalid_candidate",
                            "not_found cannot contain text or number readings.",
                            path,
                        )
                    )
                continue
            if (
                not isinstance(value.get("raw_text"), str)
                or not value["raw_text"].strip()
            ):
                diagnostics.append(
                    _error(
                        "invalid_candidate_text",
                        "Candidate raw text is required.",
                        path,
                    )
                )
                continue
            if status != "found" or value.get("conflict_group") is not None:
                severity = (
                    Severity.WARNING if name == "address_locality" else Severity.ERROR
                )
                diagnostics.append(
                    Diagnostic(
                        "intake",
                        "uncertain_candidate",
                        "Candidate requires explicit review/selection.",
                        path,
                        severity,
                    )
                )
            active[name].append(value)
        if (
            len(active[name]) > 1
            and name != "address_locality"
            and not (
                name == "technical_description"
                and _ordered_fragments(active[name], pages)
            )
        ):
            diagnostics.append(
                _error(
                    "multiple_candidates",
                    "Assemble or select candidates explicitly before intake.",
                    f"$.{name}",
                )
            )
    for index, warning in enumerate(evidence.get("warnings", [])):
        if not isinstance(warning, Mapping):
            diagnostics.append(
                _error("invalid_extraction_warning", "Warning must be a mapping.")
            )
            continue
        code = warning.get("code", "unknown_warning")
        severity = Severity.WARNING if code in _INFORMATIONAL else Severity.ERROR
        diagnostics.append(
            Diagnostic(
                "extraction",
                str(code),
                str(warning.get("message", "Extraction warning retained.")),
                f"$.warnings[{index}]",
                severity,
            )
        )
    if evidence.get("failed_page_ids") or (
        isinstance(evidence.get("assembly"), Mapping)
        and evidence["assembly"].get("failed_page_ids")
    ):
        diagnostics.append(
            _error("failed_pages", "Failed source pages require review.")
        )
    references: list[object] = []
    areas: list[object] = []
    ties: list[Course | None] = []
    for value in active["technical_description"]:
        parsed = parse_technical_description(
            value["raw_text"],
            candidate_id=value.get("candidate_id"),
            sources=[s for s in value.get("sources", []) if isinstance(s, Mapping)],
        )
        descriptions.append(parsed)
        rows.extend(parsed.rows)
        diagnostics.extend(
            d
            for d in parsed.diagnostics
            if not (
                d.code == "too_few_courses"
                and _ordered_fragments(active["technical_description"], pages)
            )
        )
        references.extend(v.value for v in parsed.reference_points)
        areas.extend(v.value for v in parsed.stated_areas)
        ties.extend(r.course for r in parsed.tie_lines)
    references.extend(v["raw_text"] for v in active["reference_point"])
    for value in active["tie_line"]:
        tie, reference = _tie_course(value["raw_text"], diagnostics)
        ties.append(tie)
        references.append(reference)
    for value in active["stated_area"]:
        number = value.get("documentary_number")
        try:
            if isinstance(number, Mapping):
                if (
                    not isinstance(number.get("unit_text"), str)
                    or _METRIC_AREA.fullmatch(number["unit_text"].strip()) is None
                ):
                    raise CourseParseError(
                        "Only square-metre stated area is supported.",
                        code="invalid_stated_area",
                    )
                areas.append(parse_distance(number.get("value")))
            else:
                parsed = parse_technical_description(
                    "Stated area: " + value["raw_text"]
                )
                if (
                    len(parsed.stated_areas) != 1
                    or parsed.stated_areas[0].value is None
                ):
                    raise CourseParseError(
                        "Area needs an explicit supported numeric reading.",
                        code="invalid_stated_area",
                    )
                areas.append(parsed.stated_areas[0].value)
        except CourseParseError as exc:
            diagnostics.append(_error("invalid_stated_area", str(exc), "$.stated_area"))
    for key, values in (
        ("tie_point", references),
        ("declared_area", areas),
        ("name", [v["raw_text"] for v in active["parcel_identifier"]]),
    ):
        selected = _unique(values, key, diagnostics)
        if selected is not None:
            data[key] = selected
    selected_tie = _unique(ties, "tie_line", diagnostics)
    if selected_tie is not None:
        data["tie_line"] = selected_tie.to_json_value()
    return _finish(data, rows, descriptions, diagnostics, evidence)
