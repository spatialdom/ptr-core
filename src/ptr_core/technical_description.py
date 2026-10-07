"""Conservative, source-associated parcel course interpretation."""

from __future__ import annotations

import html
import json
import math
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ptr_core.bearings import BearingError, parse_bearing
from ptr_core.errors import PTRParseError
from ptr_core.models import Course
from ptr_core.validation import Diagnostic, Severity, ValidationResult

_NUMBER = re.compile(
    r"(?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+)(?:\.[0-9]+)?"
    r"(?:[eE][+-]?[0-9]+)?"
)
_COURSE = re.compile(
    r"(?P<bearing>.+?)[\s,]+(?P<distance>[^\s]+)\s*"
    r"(?:meters?|metres?|m)\.?"
    r"(?:\s+to\s+(?:point\s+[\"\u201c\u201d]?(?P<point>[0-9]+)"
    r"[\"\u201c\u201d]?|(?P<return>(?:the\s+)?point\s+of\s+beginning)))?",
    re.IGNORECASE | re.DOTALL,
)
_ANCHOR = re.compile(
    r"\bthence\b|\b(?:Beginning|eginning)\b(?=\s+at\b)|\bReference point:|"
    r"\bStated area:|\bcontaining\s+an?\s+area\s+of\b",
    re.IGNORECASE,
)
_TIE = re.compile(
    r"Beginning\b.*?\bbeing\s+(?P<course>.+?)\s+from\s+(?P<reference>.+)",
    re.IGNORECASE | re.DOTALL,
)
_AREA = re.compile(
    r"(?:Stated area:|containing\s+an?\s+area\s+of)\s*"
    r"(?P<number>.+?)\s+(?:square\s+(?:meters?|metres?)"
    r"(?:\s+and\s+[\w\s-]+?square\s+decimeters?)?"
    r"|sq\.?\s*m\.?|sqm|m2)"
    r"(?:\s*\((?P<numeric>[\d,]+(?:\.\d+)?)\))?"
    r"(?:,\s*more or less)?",
    re.IGNORECASE | re.DOTALL,
)
_QUOTED_REFERENCE = re.compile(
    r'(?:\bfrom\s+|\bReference point:\s*)(?P<quoted>"(?:\\.|[^"\\])*")',
    re.IGNORECASE,
)


class CourseParseError(PTRParseError):
    """Standalone input rejection with a stable diagnostic code."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def parse_distance(value: object) -> float:
    """Parse positive finite metres, with strict grouping and no unit inference."""
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise CourseParseError("Distance must be numeric.", code="invalid_distance")
    if isinstance(value, str):
        if _NUMBER.fullmatch(value.strip()) is None:
            raise CourseParseError("Invalid numeric distance.", code="invalid_distance")
        value = value.strip().replace(",", "")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise CourseParseError(
            "Invalid numeric distance.", code="invalid_distance"
        ) from exc
    if not math.isfinite(number) or number <= 0:
        raise CourseParseError(
            "Distance must be positive and finite.", code="invalid_distance"
        )
    return number


def parse_course(bearing: str, distance: object) -> Course:
    """Shared manual/structured boundary and tie-line normalization."""
    try:
        parsed = parse_bearing(bearing)
    except BearingError as exc:
        raise CourseParseError(str(exc), code=exc.code) from exc
    return Course(parsed, parse_distance(distance))


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Half-open Unicode offsets in the exact input, with opaque source links."""

    start: int
    end: int
    text: str
    candidate_id: str | None = None
    sources: tuple[Mapping[str, Any], ...] = ()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "candidate_id": self.candidate_id,
            "sources": deepcopy([dict(s) for s in self.sources]),
        }


@dataclass(frozen=True, slots=True)
class ParsedCourse:
    """One ordered row, including an unsuccessful course without dropping it."""

    course: Course | None
    span: SourceSpan
    destination_point: int | None = None
    returns_to_beginning: bool = False
    reference_point: str | None = None
    diagnostics: tuple[Diagnostic, ...] = ()
    distance_text: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "course": self.course.to_json_value() if self.course else None,
            "span": self.span.to_mapping(),
            "destination_point": self.destination_point,
            "returns_to_beginning": self.returns_to_beginning,
            "reference_point": self.reference_point,
            "distance_text": self.distance_text,
            "diagnostics": ValidationResult(self.diagnostics).to_mapping()[
                "diagnostics"
            ],
        }


@dataclass(frozen=True, slots=True)
class ParsedValue:
    value: str | float | None
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class TechnicalDescriptionResult:
    rows: tuple[ParsedCourse, ...] = ()
    tie_lines: tuple[ParsedCourse, ...] = ()
    reference_points: tuple[ParsedValue, ...] = ()
    stated_areas: tuple[ParsedValue, ...] = ()
    unparsed_spans: tuple[SourceSpan, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "complete": self.complete,
            "rows": [row.to_mapping() for row in self.rows],
            "tie_lines": [row.to_mapping() for row in self.tie_lines],
            "reference_points": [
                {"value": value.value, "span": value.span.to_mapping()}
                for value in self.reference_points
            ],
            "stated_areas": [
                {"value": value.value, "span": value.span.to_mapping()}
                for value in self.stated_areas
            ],
            "unparsed_spans": [span.to_mapping() for span in self.unparsed_spans],
            "diagnostics": ValidationResult(self.diagnostics).to_mapping()[
                "diagnostics"
            ],
        }

    @property
    def courses(self) -> tuple[Course, ...]:
        """Successful courses; use rows to retain unsuccessful positions."""
        return tuple(row.course for row in self.rows if row.course is not None)

    @property
    def complete(self) -> bool:
        return len(self.courses) >= 3 and not any(
            d.severity is Severity.ERROR for d in self.diagnostics
        )


def _diagnostic(code: str, message: str, span: SourceSpan) -> Diagnostic:
    return Diagnostic(
        "interpretation", code, message, f"$.text[{span.start}:{span.end}]"
    )


def _reference(text: str) -> str:
    if text.startswith('"'):
        value = json.loads(text)
        if not isinstance(value, str):
            raise ValueError("Reference point must be text.")
        return value
    if not text:
        raise ValueError("Reference point text is missing.")
    return text


def _parse_row(text: str, span: SourceSpan) -> ParsedCourse:
    text = html.unescape(text).strip()
    text = re.sub(r"^thence\s*", "", text, flags=re.IGNORECASE).strip()
    match = _COURSE.fullmatch(text)
    if match is None:
        code = "unrecognized_course"
        if not re.search(r"\b(?:m|meters?|metres?)\b", text, re.I):
            bearing_text = re.split(r"\s+to\s+", text, maxsplit=1, flags=re.I)[0]
            try:
                parse_bearing(bearing_text.rstrip(" ,"))
            except BearingError:
                pass
            else:
                code = "missing_distance"
        diagnostic = _diagnostic(
            code, "Course syntax is incomplete or unsupported.", span
        )
        return ParsedCourse(None, span, diagnostics=(diagnostic,))
    try:
        course = parse_course(match["bearing"].rstrip(" ,"), match["distance"])
    except CourseParseError as exc:
        return ParsedCourse(
            None, span, diagnostics=(_diagnostic(exc.code, str(exc), span),)
        )
    destination = int(match["point"]) if match["point"] else None
    if destination is not None and destination < 1:
        diagnostic = _diagnostic(
            "invalid_destination", "Point labels must be positive.", span
        )
        return ParsedCourse(None, span, diagnostics=(diagnostic,))
    return ParsedCourse(
        course,
        span,
        destination,
        bool(match["return"]),
        distance_text=match["distance"].replace(",", ""),
    )


def _area_number(amount: str) -> float:
    """Explicit documentary numeric wrappers or unambiguous number words."""
    if _NUMBER.fullmatch(amount):
        return parse_distance(amount)
    small = dict(
        zip(
            [
                "zero",
                "one",
                "two",
                "three",
                "four",
                "five",
                "six",
                "seven",
                "eight",
                "nine",
                "ten",
                "eleven",
                "twelve",
                "thirteen",
                "fourteen",
                "fifteen",
                "sixteen",
                "seventeen",
                "eighteen",
                "nineteen",
            ],
            range(20),
            strict=True,
        )
    )
    small.update(
        dict(
            zip(
                [
                    "twenty",
                    "thirty",
                    "forty",
                    "fifty",
                    "sixty",
                    "seventy",
                    "eighty",
                    "ninety",
                ],
                range(20, 100, 10),
                strict=True,
            )
        )
    )
    scales = {"thousand": 1000, "million": 1000000, "billion": 1000000000}
    total = group = 0
    for word in amount.lower().replace("-", " ").split():
        if word == "and":
            continue
        if word in small:
            group += small[word]
        elif word == "hundred":
            group = max(group, 1) * 100
        elif word in scales:
            total += max(group, 1) * scales[word]
            group = 0
        else:
            raise CourseParseError(
                "Unsupported stated-area syntax.", code="invalid_stated_area"
            )
    return parse_distance(total + group)


def parse_technical_description(
    text: str,
    *,
    candidate_id: str | None = None,
    sources: Sequence[Mapping[str, Any]] = (),
) -> TechnicalDescriptionResult:
    """Interpret supported text while retaining all raw and unsuccessful spans.

    Thence clauses may wrap across lines. Without thence anchors, one manual
    course per line/semicolon is supported. Page assembly belongs to callers.
    """
    if not isinstance(text, str):
        raise PTRParseError("Technical description must be a string.")
    source_links = tuple(deepcopy(dict(s)) for s in sources)
    rows: list[ParsedCourse] = []
    ties: list[ParsedCourse] = []
    references: list[ParsedValue] = []
    areas: list[ParsedValue] = []
    unparsed: list[SourceSpan] = []
    diagnostics: list[Diagnostic] = []
    # JSON-quoted reference metadata can contain semicolons and anchor words.
    # Mask only those strings, preserving all original offsets and course quotes.
    masked = list(text)
    for quoted in _QUOTED_REFERENCE.finditer(text):
        start, end = quoted.span("quoted")
        masked[start:end] = " " * (end - start)
    scan_text = "".join(masked)
    anchors = list(_ANCHOR.finditer(scan_text))
    ranges: list[tuple[int, int, bool]] = []
    if anchors:
        cursor = 0
        for index, anchor in enumerate(anchors):
            if cursor < anchor.start():
                ranges.append((cursor, anchor.start(), False))
            limit = (
                anchors[index + 1].start() if index + 1 < len(anchors) else len(text)
            )
            separator = scan_text.find(";", anchor.start(), limit)
            end = separator if separator >= 0 else limit
            ranges.append((anchor.start(), end, True))
            cursor = end
        if cursor < len(text):
            ranges.append((cursor, len(text), False))
    else:
        ranges = [(m.start(), m.end(), True) for m in re.finditer(r"[^;\r\n]+", text)]
    for start, end, anchored in ranges:
        raw = text[start:end]
        body = raw.strip(" \t\r\n;:,.")
        if not body:
            continue
        span = SourceSpan(start, end, raw, candidate_id, source_links)
        if re.match(r"(?:e?ginning|Beginning)\b", body, re.I):
            if not re.search(r"\bbeing\b", body, re.I):
                unparsed.append(span)
                diagnostics.append(
                    Diagnostic(
                        "interpretation",
                        "unparsed_context",
                        "Beginning-point wording retained without a tie line.",
                        f"$.text[{start}:{end}]",
                        Severity.INFO,
                    )
                )
                continue
            match = _TIE.fullmatch(body)
            if match is None:
                row = ParsedCourse(
                    None,
                    span,
                    diagnostics=(
                        _diagnostic(
                            "unrecognized_tie_line",
                            "Tie-line syntax is unsupported.",
                            span,
                        ),
                    ),
                )
            else:
                parsed = _parse_row(match["course"], span)
                try:
                    reference = _reference(match["reference"].rstrip(" ,"))
                except (ValueError, json.JSONDecodeError):
                    reference = None
                errors = parsed.diagnostics
                if reference is None:
                    errors += (
                        _diagnostic(
                            "invalid_reference", "Reference text is invalid.", span
                        ),
                    )
                row = ParsedCourse(
                    parsed.course,
                    span,
                    reference_point=reference,
                    diagnostics=errors,
                    distance_text=parsed.distance_text,
                )
                if reference is not None:
                    references.append(ParsedValue(reference, span))
            ties.append(row)
            diagnostics.extend(row.diagnostics)
            if row.diagnostics:
                unparsed.append(span)
        elif re.match(r"Reference point:", body, re.I):
            try:
                value = _reference(body.split(":", 1)[1].strip())
                references.append(ParsedValue(value, span))
            except ValueError:
                unparsed.append(span)
                diagnostics.append(
                    _diagnostic("invalid_reference", "Reference text is invalid.", span)
                )
        elif re.match(r"Stated area:|containing\s+an?\s+area\s+of", body, re.I):
            match = _AREA.fullmatch(body)
            try:
                if match is None:
                    raise CourseParseError(
                        "Unsupported stated-area syntax.", code="invalid_stated_area"
                    )
                amount = match["number"].strip()
                parenthesized = re.fullmatch(r"([A-Za-z\s-]+)\(([\d,.]+)\)", amount)
                numeric = match["numeric"] or (
                    parenthesized[2] if parenthesized else None
                )
                wording = parenthesized[1].strip() if parenthesized else amount
                area = _area_number(numeric or wording)
                areas.append(ParsedValue(area, span))
                if numeric and "decimeter" not in body.lower():
                    word_area = _area_number(wording)
                    if word_area != area:
                        areas.append(ParsedValue(word_area, span))
                        diagnostics.append(
                            _diagnostic(
                                "conflicting_stated_area",
                                "Written and numeric stated areas disagree. "
                                "Review both.",
                                span,
                            )
                        )
            except CourseParseError as exc:
                areas.append(ParsedValue(None, span))
                unparsed.append(span)
                diagnostics.append(_diagnostic("invalid_stated_area", str(exc), span))
        elif re.match(r"thence\b", body, re.I) or (anchored and not anchors):
            if body == "Generated technical description":
                continue
            row = _parse_row(body, span)
            rows.append(row)
            diagnostics.extend(row.diagnostics)
            if row.course is None:
                unparsed.append(span)
        else:
            unparsed.append(span)
            diagnostics.append(
                Diagnostic(
                    "interpretation",
                    "unparsed_context",
                    "Uninterpreted source context retained.",
                    f"$.text[{start}:{end}]",
                    Severity.INFO,
                )
            )
    if re.search(r"\b(?:continued on|continuation|to be continued)\b", scan_text, re.I):
        diagnostics.append(
            Diagnostic(
                "interpretation",
                "unresolved_continuation",
                "Continuation wording requires explicit downstream review.",
            )
        )
    if len([r for r in rows if r.course is not None]) < 3:
        diagnostics.append(
            Diagnostic(
                "interpretation",
                "too_few_courses",
                "At least three boundary courses are required.",
            )
        )
    return TechnicalDescriptionResult(
        tuple(rows),
        tuple(ties),
        tuple(references),
        tuple(areas),
        tuple(unparsed),
        tuple(diagnostics),
    )
