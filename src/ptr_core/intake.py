"""Generic parcel intake; documentary evidence stays outside PTR."""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

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


@dataclass(frozen=True, slots=True)
class ParcelInput:
    """Parcel readings with opaque evidence and caller-supplied diagnostics.

    Source/context mappings are copied, never interpreted. Caller error
    diagnostics block record creation while preserving all parsed evidence.
    """

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
    diagnostics: tuple[Diagnostic, ...] = ()


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
            None,
            span,
            diagnostics=(*errors, _error(exc.code, str(exc), f"$.courses[{index}]")),
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
    if not isinstance(source, ParcelInput):
        raise TypeError(
            "intake_parcel expects text or ParcelInput; adapt external inputs first."
        )
    diagnostics = list(source.diagnostics)
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
        "diagnostics": [
            {
                "layer": d.layer,
                "code": d.code,
                "message": d.message,
                "path": d.path,
                "severity": d.severity.value,
            }
            for d in source.diagnostics
        ],
    }
    return _finish(data, rows, descriptions, diagnostics, evidence, source.reviewed)


def intake_candidate(source: str | ParcelInput) -> IntakeResult:
    """Deprecated name for neutral intake; external mappings need an adapter."""
    warnings.warn(
        "intake_candidate is deprecated; adapt external inputs to ParcelInput "
        "and call intake_parcel. See docs/MIGRATION.md.",
        DeprecationWarning,
        stacklevel=2,
    )
    return intake_parcel(source)
