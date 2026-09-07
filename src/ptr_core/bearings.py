"""Bearing parsing and canonical serialization for PTR v0.1."""

from __future__ import annotations

import re
from dataclasses import dataclass


class BearingError(ValueError):
    """Raised when a bearing is invalid or ambiguous."""


_CANONICAL_RE = re.compile(
    r"^(?P<cardinal>[NESW])$|"
    r"^(?P<ns>[NS])(?P<deg>0|[1-9]|[1-8][0-9])-(?P<min>[0-5][0-9])"
    r"(?:-(?P<sec>[0-5][0-9]))?(?P<ew>[EW])$"
)
_AMBIGUOUS_RE = re.compile(r"^[NS]\d{1,2}[EW]\d{1,2}(?:\D|$)", re.IGNORECASE)
_DMS_RE = re.compile(
    r"^(?P<ns>[NS])\s*"
    r"(?P<deg>\d{1,3})\s*(?:-|DEG|D|\u00b0|\s)\s*"
    r"(?P<min>\d{1,2})\s*(?:'|\u2032|M)?\s*"
    r"(?:(?:-\s*(?P<sec_hyphen>\d{1,2})\s*(?:\"|\u2033|S)?)|"
    r"(?:(?:\s+)?(?P<sec_marked>\d{1,2})\s*(?:\"|\u2033|S)))?\s*"
    r"(?P<ew>[EW])$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Bearing:
    """Immutable computational representation of a PTR v0.1 bearing.

    ``offset_degrees`` is measured away from the north/south axis for quadrant
    bearings. Cardinal bearings have no quadrant axes and no offset components.
    """

    canonical: str
    start_axis: str | None
    end_axis: str | None
    degrees: int | None
    minutes: int | None
    seconds: int | None
    azimuth_degrees: float

    @property
    def is_cardinal(self) -> bool:
        return self.start_axis is None

    @property
    def offset_degrees(self) -> float:
        if self.degrees is None or self.minutes is None:
            return 0.0
        return self.degrees + self.minutes / 60 + (self.seconds or 0) / 3600

    def __str__(self) -> str:
        return self.canonical


def parse_bearing(value: str, *, normalize: bool = True) -> Bearing:
    """Parse a bearing string into an immutable computational representation.

    Canonical PTR v0.1 bearings are always accepted. If ``normalize`` is true,
    explicitly unambiguous display/input variants are normalized before parsing.
    Ambiguous values are rejected instead of guessed.
    """

    if not isinstance(value, str):
        raise BearingError("Bearing must be a string.")

    canonical = value if _is_canonical_text(value) else None
    if canonical is None:
        if not normalize:
            raise BearingError(f"Bearing is not canonical PTR v0.1 syntax: {value!r}.")
        canonical = _normalize_bearing_text(value)

    return _bearing_from_canonical(canonical)


def is_canonical_bearing(value: object) -> bool:
    return isinstance(value, str) and _is_canonical_text(value)


def _is_canonical_text(value: str) -> bool:
    match = _CANONICAL_RE.fullmatch(value)
    if match is None:
        return False
    if match.group("cardinal") is not None:
        return True
    return _valid_quadrant_numbers(
        match.group("deg"), match.group("min"), match.group("sec")
    )


def _normalize_bearing_text(value: str) -> str:
    text = value.strip()
    if not text:
        raise BearingError("Bearing is empty.")

    upper = text.upper()
    if upper in {"N", "E", "S", "W"}:
        return upper

    compact = re.sub(r"\s+", "", upper)
    if _AMBIGUOUS_RE.match(compact):
        raise BearingError(f"Ambiguous bearing syntax: {value!r}.")

    match = _DMS_RE.fullmatch(upper)
    if match is None:
        raise BearingError(f"Invalid or ambiguous bearing syntax: {value!r}.")

    deg_text = match.group("deg")
    min_text = match.group("min")
    sec_text = match.group("sec_hyphen") or match.group("sec_marked")

    if len(deg_text) > 1 and deg_text.startswith("0"):
        raise BearingError("Degrees must not contain leading zeroes.")

    degree = int(deg_text)
    minute = int(min_text)
    second = int(sec_text) if sec_text is not None else None

    if len(min_text) != 2:
        raise BearingError("Minutes must contain exactly two digits.")
    if sec_text is not None and len(sec_text) != 2:
        raise BearingError("Seconds must contain exactly two digits.")
    if second == 0:
        second = None

    _validate_quadrant_values(degree, minute, second)

    canonical = f"{match.group('ns').upper()}{degree}-{minute:02d}"
    if second is not None:
        canonical += f"-{second:02d}"
    canonical += match.group("ew").upper()
    return canonical


def _bearing_from_canonical(value: str) -> Bearing:
    match = _CANONICAL_RE.fullmatch(value)
    if match is None:
        raise BearingError(f"Invalid canonical bearing: {value!r}.")

    cardinal = match.group("cardinal")
    if cardinal is not None:
        return Bearing(
            canonical=cardinal,
            start_axis=None,
            end_axis=None,
            degrees=None,
            minutes=None,
            seconds=None,
            azimuth_degrees={"N": 0.0, "E": 90.0, "S": 180.0, "W": 270.0}[
                cardinal
            ],
        )

    degree = int(match.group("deg"))
    minute = int(match.group("min"))
    second_text = match.group("sec")
    second = int(second_text) if second_text is not None else None
    _validate_quadrant_values(degree, minute, second)
    ns = match.group("ns")
    ew = match.group("ew")
    offset = degree + minute / 60 + (second or 0) / 3600

    if ns == "N" and ew == "E":
        azimuth = offset
    elif ns == "S" and ew == "E":
        azimuth = 180 - offset
    elif ns == "S" and ew == "W":
        azimuth = 180 + offset
    else:
        azimuth = 360 - offset

    return Bearing(
        canonical=value,
        start_axis=ns,
        end_axis=ew,
        degrees=degree,
        minutes=minute,
        seconds=second,
        azimuth_degrees=azimuth,
    )


def _valid_quadrant_numbers(degree: str, minute: str, second: str | None) -> bool:
    try:
        _validate_quadrant_values(
            int(degree), int(minute), int(second) if second is not None else None
        )
    except BearingError:
        return False
    return second != "00"


def _validate_quadrant_values(
    degree: int, minute: int, second: int | None
) -> None:
    if not 0 <= degree <= 89:
        raise BearingError("Degrees must be from 0 through 89.")
    if not 0 <= minute <= 59:
        raise BearingError("Minutes must be from 00 through 59.")
    if second is not None and not 1 <= second <= 59:
        raise BearingError("Seconds must be from 01 through 59 when present.")

    offset = degree + minute / 60 + (second or 0) / 3600
    if not 0 < offset < 90:
        raise BearingError(
            "Quadrant angular offset must be greater than 0 and less than 90 degrees."
        )
