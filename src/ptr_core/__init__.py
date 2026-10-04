"""PTR Core public API."""

from ptr_core.bearings import Bearing, BearingError, parse_bearing
from ptr_core.comparisons import (
    BoundingBox,
    ComparisonResult,
    CourseComparison,
    compare_parcels,
)
from ptr_core.errors import (
    PTRError,
    PTRParseError,
    PTRSerializationError,
    PTRUnsupportedVersionError,
)
from ptr_core.exports import to_geojson, to_wkt
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
from ptr_core.geometry_to_courses import (
    GeometryToCoursesError,
    PTRCourseCandidate,
    derive_courses_from_polygon,
)
from ptr_core.georeferencing import (
    GeoreferencedParcel,
    GeoreferencingError,
    georeference,
)
from ptr_core.io import (
    dump_ptr,
    dumps_ptr,
    load_ptr,
    load_ptr_mapping,
    load_ptr_text,
)
from ptr_core.models import Course, PTRRecord
from ptr_core.qa import QAReport, qa_report
from ptr_core.topology import TopologyResult, analyze_topology
from ptr_core.transforms import (
    TransformedParcel,
    TransformError,
    TransformStep,
    rotate,
    transform_crs,
    translate,
)
from ptr_core.validation import Diagnostic, Severity, ValidationResult, validate

__all__ = [
    "Bearing",
    "BearingError",
    "AreaComparison",
    "BoundingBox",
    "Closure",
    "ComparisonResult",
    "Course",
    "CourseComparison",
    "DerivedParcel",
    "Diagnostic",
    "GeometryToCoursesError",
    "GeoreferencedParcel",
    "GeoreferencingError",
    "ParcelMetrics",
    "PTRError",
    "PTRRecord",
    "PTRParseError",
    "PTRSerializationError",
    "PTRUnsupportedVersionError",
    "PTRCourseCandidate",
    "Point",
    "QAReport",
    "Severity",
    "TopologyResult",
    "TransformError",
    "TransformStep",
    "TransformedParcel",
    "ValidationResult",
    "Vector",
    "analyze_topology",
    "compare_parcels",
    "compute_metrics",
    "course_to_vector",
    "derive_courses_from_polygon",
    "dump_ptr",
    "dumps_ptr",
    "georeference",
    "load_ptr",
    "load_ptr_mapping",
    "load_ptr_text",
    "parse_bearing",
    "qa_report",
    "reconstruct",
    "rotate",
    "to_geojson",
    "to_wkt",
    "transform_crs",
    "translate",
    "validate",
]

__version__ = "0.1.1"
SUPPORTED_PTR_VERSIONS = ("0.1",)
