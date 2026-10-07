"""Deterministic projections of existing documentary PTR courses."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ptr_core.errors import PTRParseError
from ptr_core.models import Course, PTRRecord
from ptr_core.validation import Diagnostic, Severity, validate


class PTRFormattingError(PTRParseError):
    """A record cannot be formatted faithfully; diagnostics explain why."""

    def __init__(self, diagnostics: tuple[Diagnostic, ...]) -> None:
        super().__init__("; ".join(d.message for d in diagnostics))
        self.diagnostics = diagnostics


@dataclass(frozen=True, slots=True)
class CourseRow:
    bearing: str
    distance: float

    def to_mapping(self) -> dict[str, str | float]:
        return {"bearing": self.bearing, "distance": self.distance}


@dataclass(frozen=True, slots=True)
class ManualTableProjection:
    """Editable boundary rows and supporting metadata, kept separately."""

    rows: tuple[CourseRow, ...]
    metadata: Mapping[str, Any]
    extensions: Mapping[str, Any]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "rows": [row.to_mapping() for row in self.rows],
            "metadata": deepcopy(dict(self.metadata)),
            "extensions": deepcopy(dict(self.extensions)),
        }

    def to_ptr_mapping(self) -> dict[str, Any]:
        """Lossless stored PTR projection, including unknown extension values."""
        data = deepcopy(dict(self.metadata))
        data["lines"] = [[row.bearing, row.distance] for row in self.rows]
        data.update(deepcopy(dict(self.extensions)))
        return data


@dataclass(frozen=True, slots=True)
class GeneratedDescription:
    """Generated prose, with explicit limits and no source-text claim."""

    text: str
    omitted_fields: tuple[str, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()


def _require_record(record: PTRRecord) -> None:
    diagnostics = validate(record).errors
    known = {
        "ptr_version",
        "lines",
        "name",
        "record_id",
        "tie_point",
        "tie_line",
        "declared_area",
    }
    if known.intersection(record.extra):
        diagnostics += (
            Diagnostic(
                "formatting",
                "extension_field_collision",
                "Extensions must not override defined PTR fields.",
            ),
        )
    try:
        json.dumps(record.to_mapping(), allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        diagnostics += (
            Diagnostic(
                "serialization",
                "invalid_extension_value",
                "PTR values must be JSON serializable and finite.",
            ),
        )
    if diagnostics:
        raise PTRFormattingError(diagnostics)


def project_manual_table(record: PTRRecord) -> ManualTableProjection:
    """Project canonical boundary rows without geometry or numeric rounding."""
    _require_record(record)
    metadata = record.to_mapping(include_extra=False)
    metadata.pop("lines")
    return ManualTableProjection(
        tuple(CourseRow(c.bearing.canonical, c.distance) for c in record.lines),
        deepcopy(metadata),
        deepcopy(dict(record.extra)),
    )


def _course_text(course: Course) -> str:
    canonical = course.bearing.canonical
    if len(canonical) == 1:
        bearing = {
            "N": "Due North",
            "E": "Due East",
            "S": "Due South",
            "W": "Due West",
        }[canonical]
    else:
        bearing = f"{canonical[0]} {canonical[1:-1]} {canonical[-1]}"
    return f"{bearing}, {course.distance} metres"


def to_technical_description(record: PTRRecord) -> GeneratedDescription:
    """Generate readable course prose, never verbatim/certified survey wording."""
    _require_record(record)
    lines = ["Generated technical description."]
    if record.tie_point is not None:
        reference = json.dumps(record.tie_point, ensure_ascii=False)
        if record.tie_line is not None:
            lines.append(
                f"Beginning at point 1, being {_course_text(record.tie_line)} "
                f"from {reference};"
            )
        else:
            lines.append(f"Reference point: {reference};")
    lines.extend(f"Thence {_course_text(course)};" for course in record.lines)
    if record.declared_area is not None:
        lines.append(f"Stated area: {record.declared_area} square metres;")
    omitted = tuple(
        [key for key in ("name", "record_id") if getattr(record, key) is not None]
        + [f"extra.{key}" for key in sorted(record.extra)]
    )
    diagnostics: tuple[Diagnostic, ...] = ()
    if omitted:
        diagnostics = (
            Diagnostic(
                "formatting",
                "metadata_not_in_prose",
                "Use the structured table projection to preserve omitted metadata.",
                severity=Severity.WARNING,
            ),
        )
    return GeneratedDescription("\n".join(lines) + "\n", omitted, diagnostics)


# Preserve the original public name, including its signature and exceptions.
format_technical_description = to_technical_description
