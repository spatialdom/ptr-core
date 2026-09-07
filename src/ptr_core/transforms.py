"""Explicit transforms for derived parcel geometries."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin
from typing import Any

from pyproj import Transformer

from ptr_core.geometry import DerivedParcel, Point
from ptr_core.georeferencing import GeoreferencedParcel


class TransformError(ValueError):
    """Raised when an explicit transform cannot be performed."""


@dataclass(frozen=True, slots=True)
class TransformStep:
    operation: str
    parameters: dict[str, float | str | None]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True, slots=True)
class TransformedParcel:
    """Separate transformed geometry that preserves its source PTR record."""

    source: DerivedParcel | GeoreferencedParcel | TransformedParcel
    crs: str | None
    vertices: tuple[Point, ...]
    final_endpoint: Point
    transform_steps: tuple[TransformStep, ...]

    @property
    def local(self) -> DerivedParcel:
        if isinstance(self.source, DerivedParcel):
            return self.source
        return self.source.local


TransformableParcel = DerivedParcel | GeoreferencedParcel | TransformedParcel


def translate(
    parcel: TransformableParcel,
    *,
    dx: float,
    dy: float,
) -> TransformedParcel:
    """Translate derived geometry by explicit coordinate offsets."""

    step = TransformStep("translate", {"dx": dx, "dy": dy, "crs": _crs(parcel)})
    return TransformedParcel(
        source=parcel,
        crs=_crs(parcel),
        vertices=tuple(Point(point.x + dx, point.y + dy) for point in parcel.vertices),
        final_endpoint=Point(
            parcel.final_endpoint.x + dx, parcel.final_endpoint.y + dy
        ),
        transform_steps=(*_steps(parcel), step),
    )


def rotate(
    parcel: TransformableParcel,
    *,
    angle_degrees: float,
    origin: Point,
) -> TransformedParcel:
    """Rotate derived geometry around an explicit origin/reference point."""

    step = TransformStep(
        "rotate",
        {
            "angle_degrees": angle_degrees,
            "origin_x": origin.x,
            "origin_y": origin.y,
            "crs": _crs(parcel),
        },
    )
    return TransformedParcel(
        source=parcel,
        crs=_crs(parcel),
        vertices=tuple(
            _rotate_point(point, angle_degrees=angle_degrees, origin=origin)
            for point in parcel.vertices
        ),
        final_endpoint=_rotate_point(
            parcel.final_endpoint, angle_degrees=angle_degrees, origin=origin
        ),
        transform_steps=(*_steps(parcel), step),
    )


def transform_crs(
    parcel: TransformableParcel,
    *,
    source_crs: str,
    target_crs: str,
) -> TransformedParcel:
    """Transform coordinates between explicitly supplied CRS definitions."""

    if not source_crs or not source_crs.strip():
        raise TransformError("source_crs must be supplied explicitly.")
    if not target_crs or not target_crs.strip():
        raise TransformError("target_crs must be supplied explicitly.")
    parcel_crs = _crs(parcel)
    if parcel_crs is not None and parcel_crs != source_crs:
        raise TransformError("source_crs does not match the parcel CRS metadata.")

    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    step = TransformStep(
        "transform_crs",
        {"source_crs": source_crs, "target_crs": target_crs},
    )
    return TransformedParcel(
        source=parcel,
        crs=target_crs,
        vertices=tuple(
            _transform_point(point, transformer) for point in parcel.vertices
        ),
        final_endpoint=_transform_point(parcel.final_endpoint, transformer),
        transform_steps=(*_steps(parcel), step),
    )


def _rotate_point(point: Point, *, angle_degrees: float, origin: Point) -> Point:
    angle = radians(angle_degrees)
    translated_x = point.x - origin.x
    translated_y = point.y - origin.y
    return Point(
        origin.x + translated_x * cos(angle) - translated_y * sin(angle),
        origin.y + translated_x * sin(angle) + translated_y * cos(angle),
    )


def _transform_point(point: Point, transformer: Transformer) -> Point:
    x, y = transformer.transform(point.x, point.y)
    return Point(float(x), float(y))


def _crs(parcel: TransformableParcel) -> str | None:
    if isinstance(parcel, GeoreferencedParcel | TransformedParcel):
        return parcel.crs
    return None


def _steps(parcel: TransformableParcel) -> tuple[TransformStep, ...]:
    if isinstance(parcel, TransformedParcel):
        return parcel.transform_steps
    return ()
