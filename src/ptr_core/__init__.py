"""PTR Core public API."""

from ptr_core.bearings import Bearing, BearingError, parse_bearing
from ptr_core.errors import PTRParseError, PTRSerializationError
from ptr_core.geometry import (
    AreaComparison,
    Closure,
    DerivedParcel,
    ParcelMetrics,
    Point,
    Vector,
    compute_metrics,
    course_to_vector,
    reconstruct,
)
from ptr_core.io import (
    dump_ptr,
    dumps_ptr,
    load_ptr,
    load_ptr_mapping,
    load_ptr_text,
)
from ptr_core.models import Course, PTRRecord
from ptr_core.validation import Diagnostic, Severity, ValidationResult, validate

__all__ = [
    "Bearing",
    "BearingError",
    "AreaComparison",
    "Closure",
    "Course",
    "DerivedParcel",
    "Diagnostic",
    "ParcelMetrics",
    "PTRRecord",
    "PTRParseError",
    "PTRSerializationError",
    "Point",
    "Severity",
    "ValidationResult",
    "Vector",
    "compute_metrics",
    "course_to_vector",
    "dump_ptr",
    "dumps_ptr",
    "load_ptr",
    "load_ptr_mapping",
    "load_ptr_text",
    "parse_bearing",
    "reconstruct",
    "validate",
]

__version__ = "0.1.0"
SUPPORTED_PTR_VERSIONS = ("0.1",)
