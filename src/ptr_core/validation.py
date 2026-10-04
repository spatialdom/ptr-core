"""Layered PTR v0.1 validation."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ptr_core.bearings import BearingError, parse_bearing
from ptr_core.models import PTR_VERSION


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    layer: str
    code: str
    message: str
    path: str = "$"
    severity: Severity = Severity.ERROR


@dataclass(frozen=True, slots=True)
class ValidationResult:
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def errors(self) -> tuple[Diagnostic, ...]:
        return tuple(d for d in self.diagnostics if d.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[Diagnostic, ...]:
        return tuple(d for d in self.diagnostics if d.severity is Severity.WARNING)

    @property
    def conforms(self) -> bool:
        return not self.errors

    def to_mapping(self) -> dict[str, Any]:
        return {
            "conforms": self.conforms,
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
        }


def validate(source: str | Mapping[str, Any] | object) -> ValidationResult:
    """Validate JSON text, a mapping, or a PTRRecord-like object."""

    if hasattr(source, "to_mapping"):
        source = source.to_mapping()
    if isinstance(source, str):
        try:
            data = json.loads(source)
        except json.JSONDecodeError as exc:
            return ValidationResult(
                (
                    Diagnostic(
                        "serialization",
                        "invalid_json",
                        f"Invalid JSON: {exc.msg}.",
                    ),
                )
            )
        if not isinstance(data, Mapping):
            return ValidationResult(
                (
                    Diagnostic(
                        "serialization",
                        "top_level_not_object",
                        "PTR JSON must contain a single top-level object.",
                    ),
                )
            )
        return validate_mapping(data)
    if isinstance(source, Mapping):
        return validate_mapping(source)
    return ValidationResult(
        (
            Diagnostic(
                "serialization",
                "unsupported_input",
                "Validation input must be JSON text, a mapping, or PTRRecord.",
            ),
        )
    )


def validate_mapping(
    data: Mapping[str, Any], *, accept_noncanonical_bearings: bool = False
) -> ValidationResult:
    diagnostics: list[Diagnostic] = []
    _validate_top_level(data, diagnostics)

    lines = data.get("lines")
    if isinstance(lines, Sequence) and not isinstance(lines, str | bytes):
        for index, course in enumerate(lines):
            _validate_course(
                course,
                diagnostics,
                path=f"$.lines[{index}]",
                accept_noncanonical_bearings=accept_noncanonical_bearings,
            )

    if "tie_line" in data:
        _validate_course(
            data["tie_line"],
            diagnostics,
            path="$.tie_line",
            accept_noncanonical_bearings=accept_noncanonical_bearings,
        )
        if "tie_point" not in data:
            diagnostics.append(
                Diagnostic(
                    "semantic",
                    "tie_line_without_tie_point",
                    "tie_line must not appear unless tie_point is also present.",
                    "$.tie_line",
                )
            )

    return ValidationResult(tuple(diagnostics))


def _validate_top_level(data: Mapping[str, Any], diagnostics: list[Diagnostic]) -> None:
    if "ptr_version" not in data:
        diagnostics.append(
            Diagnostic(
                "structural",
                "missing_ptr_version",
                "ptr_version is required.",
                "$.ptr_version",
            )
        )
    elif data["ptr_version"] != PTR_VERSION:
        diagnostics.append(
            Diagnostic(
                "structural",
                "unsupported_ptr_version",
                'ptr_version must be "0.1".',
                "$.ptr_version",
            )
        )

    if "lines" not in data:
        diagnostics.append(
            Diagnostic("structural", "missing_lines", "lines is required.", "$.lines")
        )
    elif not isinstance(data["lines"], list):
        diagnostics.append(
            Diagnostic(
                "structural", "lines_not_array", "lines must be an array.", "$.lines"
            )
        )
    elif len(data["lines"]) < 3:
        diagnostics.append(
            Diagnostic(
                "semantic",
                "too_few_courses",
                "lines must contain at least three boundary courses.",
                "$.lines",
            )
        )

    for field in ("name", "record_id", "tie_point"):
        if field in data and not isinstance(data[field], str):
            diagnostics.append(
                Diagnostic(
                    "structural",
                    f"{field}_not_string",
                    f"{field} must be a string.",
                    f"$.{field}",
                )
            )

    if "declared_area" in data:
        _validate_positive_json_number(
            data["declared_area"],
            diagnostics,
            path="$.declared_area",
            code_prefix="declared_area",
            semantic_message="declared_area must be greater than zero.",
        )


def _validate_course(
    value: object,
    diagnostics: list[Diagnostic],
    *,
    path: str,
    accept_noncanonical_bearings: bool,
) -> None:
    if not isinstance(value, list) or len(value) != 2:
        diagnostics.append(
            Diagnostic(
                "structural",
                "bad_course_shape",
                "Course must be a two-item array [bearing, distance].",
                path,
            )
        )
        return

    bearing, distance = value
    if not isinstance(bearing, str):
        diagnostics.append(
            Diagnostic(
                "structural",
                "bearing_not_string",
                "Course bearing must be a string.",
                f"{path}[0]",
            )
        )
    else:
        try:
            parsed = parse_bearing(bearing, normalize=accept_noncanonical_bearings)
        except BearingError as exc:
            diagnostics.append(
                Diagnostic(
                    "semantic",
                    "invalid_bearing",
                    str(exc),
                    f"{path}[0]",
                )
            )
        else:
            if parsed.canonical != bearing and not accept_noncanonical_bearings:
                diagnostics.append(
                    Diagnostic(
                        "semantic",
                        "noncanonical_bearing",
                        "Stored PTR bearing must use canonical syntax.",
                        f"{path}[0]",
                    )
                )

    _validate_positive_json_number(
        distance,
        diagnostics,
        path=f"{path}[1]",
        code_prefix="distance",
        semantic_message="Course distance must be greater than zero.",
    )


def _validate_positive_json_number(
    value: object,
    diagnostics: list[Diagnostic],
    *,
    path: str,
    code_prefix: str,
    semantic_message: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        diagnostics.append(
            Diagnostic(
                "structural",
                f"{code_prefix}_not_number",
                f"{code_prefix} must be a JSON number.",
                path,
            )
        )
        return
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value <= 0:
        diagnostics.append(
            Diagnostic(
                "semantic", f"{code_prefix}_not_positive", semantic_message, path
            )
        )
