"""Explicit tie-point georeferencing for derived PTR parcels."""

from __future__ import annotations

from dataclasses import dataclass

from ptr_core.geometry import DerivedParcel, Point, course_to_vector


class GeoreferencingError(ValueError):
    """Raised when georeferencing lacks explicit control information."""


@dataclass(frozen=True, slots=True)
class GeoreferencedParcel:
    """A separate referenced geometry derived from a local parcel."""

    local: DerivedParcel
    crs: str
    tie_point: Point
    point1: Point
    vertices: tuple[Point, ...]
    final_endpoint: Point


def georeference(
    parcel: DerivedParcel,
    *,
    tie_point: Point,
    crs: str,
) -> GeoreferencedParcel:
    """Place a local derived parcel using explicit tie-point coordinates.

    PTR v0.1 defines ``tie_line`` as the course from ``tie_point`` to Point 1.
    The caller must supply the tie-point coordinates and CRS. PTR Core never
    guesses a coordinate reference system.
    """

    if not crs or not crs.strip():
        raise GeoreferencingError("A CRS identifier must be supplied explicitly.")
    if parcel.record.tie_line is None:
        raise GeoreferencingError(
            "PTR record must contain tie_line for georeferencing."
        )

    tie_vector = course_to_vector(parcel.record.tie_line)
    point1 = Point(tie_point.x + tie_vector.dx, tie_point.y + tie_vector.dy)
    return GeoreferencedParcel(
        local=parcel,
        crs=crs,
        tie_point=tie_point,
        point1=point1,
        vertices=tuple(_translate(point, point1) for point in parcel.vertices),
        final_endpoint=_translate(parcel.final_endpoint, point1),
    )


def _translate(local: Point, point1: Point) -> Point:
    return Point(point1.x + local.x, point1.y + local.y)
