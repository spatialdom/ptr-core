"""Load and serialize PTR records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from os import PathLike
from pathlib import Path
from typing import Any

from ptr_core.bearings import BearingError, parse_bearing
from ptr_core.errors import PTRParseError, PTRSerializationError
from ptr_core.models import Course, PTRRecord
from ptr_core.validation import validate_mapping

_KNOWN_FIELDS = {
    "ptr_version",
    "name",
    "record_id",
    "tie_point",
    "tie_line",
    "lines",
    "declared_area",
}


def load_ptr(source: str | PathLike[str] | Mapping[str, Any]) -> PTRRecord:
    """Load a PTR record from a path, JSON text, or mapping."""

    if isinstance(source, Mapping):
        return load_ptr_mapping(source)
    if isinstance(source, PathLike):
        return load_ptr_text(Path(source).read_text(encoding="utf-8"))
    if isinstance(source, str):
        path = Path(source)
        if path.exists():
            return load_ptr_text(path.read_text(encoding="utf-8"))
        return load_ptr_text(source)
    raise PTRParseError("PTR source must be a path, JSON string, or mapping.")


def load_ptr_text(text: str) -> PTRRecord:
    """Load a PTR record from UTF-8 JSON text already decoded as ``str``."""

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PTRParseError(f"Invalid PTR JSON: {exc.msg}.") from exc
    if not isinstance(raw, Mapping):
        raise PTRParseError("PTR JSON must contain a single top-level object.")
    return load_ptr_mapping(raw)


def load_ptr_mapping(
    mapping: Mapping[str, Any], *, normalize_bearings: bool = False
) -> PTRRecord:
    """Load a PTR record from a Python mapping.

    Stored PTR records are strict by default and must contain canonical bearing
    strings. Set ``normalize_bearings`` only for pre-storage application input.
    """

    result = validate_mapping(mapping, accept_noncanonical_bearings=normalize_bearings)
    if not result.conforms:
        details = "; ".join(d.message for d in result.errors)
        raise PTRParseError(details or "PTR mapping is not conforming.")

    try:
        lines = tuple(
            _parse_course(course, normalize_bearings=normalize_bearings)
            for course in mapping["lines"]
        )
        tie_line = (
            _parse_course(
                mapping["tie_line"], normalize_bearings=normalize_bearings
            )
            if "tie_line" in mapping
            else None
        )
    except (BearingError, TypeError, ValueError) as exc:
        raise PTRParseError(str(exc)) from exc

    extra = {key: value for key, value in mapping.items() if key not in _KNOWN_FIELDS}

    return PTRRecord(
        ptr_version=mapping["ptr_version"],
        name=mapping.get("name"),
        record_id=mapping.get("record_id"),
        tie_point=mapping.get("tie_point"),
        tie_line=tie_line,
        lines=lines,
        declared_area=mapping.get("declared_area"),
        extra=extra,
    )


def dumps_ptr(record: PTRRecord, *, include_extra: bool = True) -> str:
    """Serialize a PTR record to canonical, deterministic JSON text."""

    try:
        return (
            json.dumps(
                record.to_mapping(include_extra=include_extra),
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        )
    except (TypeError, ValueError) as exc:
        raise PTRSerializationError(str(exc)) from exc


def dump_ptr(
    record: PTRRecord, path: str | PathLike[str], *, include_extra: bool = True
) -> None:
    """Write a PTR record to a UTF-8 JSON file."""

    Path(path).write_text(
        dumps_ptr(record, include_extra=include_extra), encoding="utf-8"
    )


def _parse_course(value: object, *, normalize_bearings: bool) -> Course:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise PTRParseError("Course must be a two-item array [bearing, distance].")
    bearing_value, distance = value
    if not isinstance(bearing_value, str):
        raise PTRParseError("Course bearing must be a string.")
    if isinstance(distance, bool) or not isinstance(distance, int | float):
        raise PTRParseError("Course distance must be a JSON number.")
    return Course(
        parse_bearing(bearing_value, normalize=normalize_bearings), float(distance)
    )
