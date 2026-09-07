"""Structured QA reporting for PTR records and derived parcels."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any

from ptr_core.errors import PTRParseError
from ptr_core.geometry import DerivedParcel, reconstruct
from ptr_core.io import load_ptr_mapping, load_ptr_text
from ptr_core.models import PTRRecord
from ptr_core.validation import Diagnostic, ValidationResult, validate


@dataclass(frozen=True, slots=True)
class QAReport:
    """Machine-readable parcel QA report."""

    validation: ValidationResult
    parcel: DerivedParcel | None = None

    @property
    def conforms(self) -> bool:
        return self.validation.conforms

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        if self.parcel is None:
            return self.validation.diagnostics
        return self.validation.diagnostics + self.parcel.qa_findings

    def to_mapping(self) -> dict[str, Any]:
        metrics = None
        if self.parcel is not None:
            metrics = _metrics_mapping(self.parcel)
        return {
            "conforms": self.conforms,
            "validation": self.validation.to_mapping(),
            "metrics": metrics,
            "findings": [_diagnostic_mapping(d) for d in self.diagnostics],
        }


def qa_report(
    source: str | PathLike[str] | Mapping[str, Any] | PTRRecord,
    *,
    closure_tolerance: float = 1e-9,
    area_tolerance: float = 1e-9,
) -> QAReport:
    """Create one deterministic QA report for validation and derived geometry."""

    record: PTRRecord | None
    if isinstance(source, PTRRecord):
        validation = validate(source)
        record = source if validation.conforms else None
    elif isinstance(source, Mapping):
        validation = validate(source)
        record = _load_mapping_if_valid(source, validation)
    else:
        text = _read_text_source(source)
        validation = validate(text)
        record = _load_text_if_valid(text, validation)

    if record is None:
        return QAReport(validation)

    return QAReport(
        validation,
        reconstruct(
            record,
            closure_tolerance=closure_tolerance,
            area_tolerance=area_tolerance,
        ),
    )


def _read_text_source(source: str | PathLike[str]) -> str:
    if isinstance(source, PathLike):
        return Path(source).read_text(encoding="utf-8")
    path = Path(source)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return source


def _load_mapping_if_valid(
    source: Mapping[str, Any], validation: ValidationResult
) -> PTRRecord | None:
    if not validation.conforms:
        return None
    try:
        return load_ptr_mapping(source)
    except PTRParseError:
        return None


def _load_text_if_valid(text: str, validation: ValidationResult) -> PTRRecord | None:
    if not validation.conforms:
        return None
    try:
        return load_ptr_text(text)
    except PTRParseError:
        return None


def _metrics_mapping(parcel: DerivedParcel) -> dict[str, Any]:
    metrics = parcel.metrics
    comparison = metrics.declared_area_comparison
    return {
        "perimeter": metrics.perimeter,
        "signed_area": metrics.signed_area,
        "area": metrics.area,
        "closure": {
            "east": metrics.closure.east,
            "north": metrics.closure.north,
            "linear": metrics.closure.linear,
            "tolerance": metrics.closure.tolerance,
            "is_closed": metrics.closure.is_closed,
        },
        "declared_area_comparison": None
        if comparison is None
        else {
            "declared_area": comparison.declared_area,
            "computed_area": comparison.computed_area,
            "absolute_difference": comparison.absolute_difference,
            "relative_difference": comparison.relative_difference,
        },
    }


def _diagnostic_mapping(diagnostic: Diagnostic) -> dict[str, str]:
    return {
        "layer": diagnostic.layer,
        "code": diagnostic.code,
        "message": diagnostic.message,
        "path": diagnostic.path,
        "severity": diagnostic.severity.value,
    }
