"""Immutable PTR v0.1 documentary domain models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from ptr_core.bearings import Bearing

PTR_VERSION = "0.1"


@dataclass(frozen=True, slots=True)
class Course:
    """Immutable documentary bearing-distance course."""

    bearing: Bearing
    distance: float

    def to_json_value(self) -> list[str | float]:
        return [self.bearing.canonical, self.distance]


@dataclass(frozen=True, slots=True)
class PTRRecord:
    """Immutable PTR v0.1 documentary record.

    ``lines`` is stored as a tuple so boundary course order is preserved and
    callers cannot accidentally mutate the source record in place.
    """

    ptr_version: str
    lines: tuple[Course, ...]
    name: str | None = None
    record_id: str | None = None
    tie_point: str | None = None
    tie_line: Course | None = None
    declared_area: float | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "lines", tuple(self.lines))
        object.__setattr__(self, "extra", MappingProxyType(dict(self.extra)))

    def to_mapping(self, *, include_extra: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {"ptr_version": self.ptr_version}
        if self.name is not None:
            data["name"] = self.name
        if self.record_id is not None:
            data["record_id"] = self.record_id
        if self.tie_point is not None:
            data["tie_point"] = self.tie_point
        if self.tie_line is not None:
            data["tie_line"] = self.tie_line.to_json_value()
        data["lines"] = [course.to_json_value() for course in self.lines]
        if self.declared_area is not None:
            data["declared_area"] = self.declared_area
        if include_extra:
            data.update(self.extra)
        return data
