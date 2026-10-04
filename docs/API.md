# PTR Core v0.1 Public API

PTR Core v0.1 exposes normal application entry points from `ptr_core`. Downstream
applications should not need to import internal modules.

## Supported PTR Versions

`SUPPORTED_PTR_VERSIONS` is `("0.1",)`.

Records using another `ptr_version` fail explicitly during loading with
`PTRUnsupportedVersionError`. Validation reports the same condition as a
structured `unsupported_ptr_version` diagnostic.

## Loading And Serialization

- `load_ptr(source)` loads from a file path, JSON text, or mapping.
- `load_ptr_text(text)` loads from JSON text.
- `load_ptr_mapping(mapping, normalize_bearings=False)` loads from a mapping.
  Stored PTR records are strict by default. Set `normalize_bearings=True` only
  for pre-storage application input.
- `dumps_ptr(record, include_extra=True)` serializes deterministic canonical
  JSON text.
- `dump_ptr(record, path, include_extra=True)` writes UTF-8 JSON.

## Bearings

- `parse_bearing(value, normalize=True)` returns an immutable `Bearing`.
- `BearingError` is raised for invalid or ambiguous bearing input.

With normalization enabled, the explicit case-insensitive words `North`, `East`,
`South`, `West` and their `Due ` variants normalize to `N/E/S/W`; surrounding
and intervening whitespace is ignored. Quadrants such as `N 45-30 E`, `N45-30E`,
and `N 45°30′ E` use the existing parser, including whole-second precision.
Unlabelled azimuths and ambiguous directions are rejected. `normalize=False`
continues to require stored canonical PTR syntax. `BearingError.code` is
`invalid_bearing`, or `noncanonical_bearing` for strict input rejection.

## Technical Description And Manual Courses

- `parse_course(bearing, distance)` returns a normalized `Course`, for both
  manual boundary courses and tie lines. `parse_distance(value)` accepts positive
  finite numeric metres or decimal/scientific strings with valid thousands
  grouping. Neither function infers units or repairs malformed numbers.
- `CourseParseError.code` is `invalid_distance` or the bearing error category.
- `parse_technical_description(text, candidate_id=None, sources=())` returns
  `TechnicalDescriptionResult`. Inputs are recovered text, never documents.

Supported course syntax is `thence <bearing>, <distance> m [to point 2]`, with
`meter(s)`/`metre(s)` spelling, optional comma, quoted destination numbers, or
explicit `to [the] point of beginning`. Thence clauses can wrap lines; manual
input without thence uses one course per line or semicolon. Cardinal aliases,
quadrants and seconds all use `parse_bearing`. Documentary axis punctuation
(`N.`, `S..`, `E.,`), degree/minute wording and curly minute quotes are explicit
input variants, while stored syntax remains strict. Leading-zero degrees,
missing components and bracketed OCR noise are rejected.

`Beginning at ... being <course> from <reference>` produces a separate tie row.
`Reference point: "..."` accepts JSON-quoted reference text. Numeric
`Stated area: <number> square metres` and `containing an area of <number> square
meters` clauses are supported for generated-description round trips; worded
area extraction belongs to PTR Extract. All alternatives remain available.

`rows` preserves every boundary position, including `course=None` on failure;
`courses` is the convenience tuple of successful courses. `tie_lines`,
`reference_points`, `stated_areas`, `unparsed_spans` and `diagnostics` are separate.
Each row has documentary `destination_point`, `returns_to_beginning`, and a
`SourceSpan`: exact text, half-open Unicode code-point offsets, candidate ID and
opaque source mappings. These offsets refer to input text, not original page
coordinates or browser UTF-16 indices. Source associations survive normalization.

`complete` requires three supported boundary courses and no error diagnostics;
it does not assert closure. Stable interpretation categories include
`invalid_bearing`, `invalid_distance`, `missing_distance`, `unrecognized_course`,
`invalid_destination`, `unrecognized_tie_line`, `invalid_reference`,
`invalid_stated_area`, `too_few_courses`, and `unresolved_continuation`.
Uninterpreted context is retained with informational `unparsed_context`.
No ordering, destination, return, geometry or missing course is inferred.

## Candidate And Manual Intake

- `intake_parcel(text_or_ParcelInput)` returns `IntakeResult` for paste/manual
  input. `ParcelInput` accepts `text`, `courses`, `tie_point`, `tie_line`,
  `declared_area`, `name`, `record_id`, `reviewed`, `sources`, and `context`.
  Structured courses may be `Course`, `[bearing, distance]`, or mappings with
  `bearing` and `distance` (also `distance_m`), plus optional `raw_text`,
  `candidate_id`, and `sources`. Numeric inputs share `parse_course` and
  `parse_distance`. Different text/structured values produce `conflicting_courses`.
- `intake_candidate(mapping_or_CandidateMapping)` consumes CandidateParcel
  schema `0.2`. `CandidateMapping` is a `to_dict()` protocol, so an extractor
  dataclass can be passed without Core importing PTR Extract. Binary documents,
  OCR packages, and an ExtractionResult wrapper are not accepted here.

`IntakeResult.record` is a conforming `PTRRecord` or `None`. `rows`,
`descriptions`, `diagnostics`, `evidence`, and `reviewed` remain outside PTR;
`to_mapping()` creates a review handoff with copied evidence and source spans.
Structured row spans refer to the retained row text representation, not page
offsets. `evidence` preserves raw/document text, IDs, source bundle/page order,
source links, provenance, confidence, address/context, and all alternatives.
Core interprets `raw_text` so parser offsets refer to that exact text; cleaned
`document_text` remains evidence. Confidence does not affect conformance.

One assembled description can span several source pages. The text extractor's
individual thence candidates are also supported when each contains one thence
clause and a single disjoint source span, already ordered according to
`source_bundle.ordered_pages` and page text offsets. Core never sorts pages or
infers continuation. Competing, overlapping, or reordered descriptions require
explicit assembly/selection. Unknown extraction warnings block record creation;
`parcel_semantics_unchecked`, missing optional area/reference/tie information,
and address alternatives remain warnings. Failed/low-quality pages and possible
missing continuation block intake even if three courses were recovered.

Ambiguous/conflicting optional PTR metadata blocks intake, rather than silently
discarding it. Address/locality is context only. Missing optional references
allow local PTR records; a tie line still requires a reference. Explicit
reference/tie/area readings must agree with text readings. Area intake accepts
positive numeric square-metre readings, including `DocumentaryNumber.value`
with a supported metric `unit_text`; number-word extraction and composite or
other-unit area readings remain the extractor/review layer's responsibility.
No new PTR fields are created for provenance, destinations, or review status.

Stable intake codes include `unsupported_candidate_version`,
`invalid_source_bundle`, `invalid_source_reference`, `invalid_provenance`,
`invalid_candidate_field`, `invalid_candidate_id`, `invalid_candidate_status`,
`invalid_candidate_text`, `invalid_candidate`, `uncertain_candidate`,
`multiple_candidates`, `conflicting_values`, `conflicting_courses`,
`invalid_tie_line`, `invalid_stated_area`, and `failed_pages`. Parser and existing
PTR validation codes are retained; extraction diagnostics use the extractor's
original code and the `extraction` layer.

```python
from ptr_core import ParcelInput, intake_candidate, intake_parcel, qa_report

manual = intake_parcel(ParcelInput(
    courses=(["Due North", "10"], ["East", 10], ["South", 10], ["West", 10]),
    reviewed=True,
))
assert manual.record is not None
report = qa_report(manual.record)  # geometry warnings do not invalidate intake

# extracted is CandidateParcel 0.2 from PTR Extract, or its JSON mapping.
# result = intake_candidate(extracted)
# downstream review keeps result.evidence and result.diagnostics separately
```

Pin downstream integrations to `ptr-core==0.1.1` once published (or to the
reviewed commit of this branch before publication). Supported PTR stays `0.1`;
CandidateParcel `0.2` is a separate input schema. Core does not change downstream
review state or write original transcriptions.

## Validation And QA

- `validate(source)` returns `ValidationResult`; expected conformance failures
  are diagnostics, not exceptions.
- `qa_report(source)` returns `QAReport`, combining validation, metrics, and
  geometric QA findings in deterministic machine-readable order.

## Geometry And Metrics

- `course_to_vector(course)` converts a documentary course into local X/Y metre
  deltas.
- `reconstruct(record)` returns `DerivedParcel` without mutating `PTRRecord`.
- `compute_metrics(parcel)` returns `ParcelMetrics`.

Local axes are X/Easting positive east and Y/Northing positive north. Point 1 is
placed at `(0, 0)` for local reconstruction only.

## Comparison

- `compare_parcels(left, right, distance_tolerance=..., area_tolerance=...)`
  returns `ComparisonResult`.

Comparison reports documentary equality, course-by-course differences, area and
perimeter differences, translation/centroid differences, vertex and boundary
distance metrics, and bounding-box overlap where frames are compatible.

Spatial comparisons are limited to local-vs-local parcels or georeferenced
parcels with the same CRS. Mixed local/georeferenced parcels or differing CRS
values return structured incompatibility instead of guessing a transformation.

Comparison never declares legal identity, ownership, cadastral correctness, or
authoritative sameness.

## Topology

- `analyze_topology(left, right, distance_tolerance=..., area_tolerance=...)`
  returns `TopologyResult`.

Topology analysis reports compatible-frame status, equality, containment,
overlap area, point-touching, shared-edge adjacency, shared-boundary length/WKT,
and gap distance. It uses Shapely/GEOS behind the PTR Core API for robust
polygon relationships. Tolerances are explicit inputs and classify near
relationships; parcel geometries are not snapped or repaired.

## Transforms

- `translate(parcel, dx=..., dy=...)` returns `TransformedParcel`.
- `rotate(parcel, angle_degrees=..., origin=Point(...))` returns
  `TransformedParcel`.
- `transform_crs(parcel, source_crs="...", target_crs="...")` returns
  `TransformedParcel`.

Translation and rotation are local rigid-body operations and do not rescale
survey distances. CRS transformation requires explicit source and target CRS
definitions and records reproducible transform metadata. Transforms return
separate geometry objects; they never edit the source PTR record.

## Geometry To Courses

- `derive_courses_from_polygon(geometry, coordinate_frame=..., distance_decimals=12)`
  returns `PTRCourseCandidate`.

This inverse operation accepts a simple polygon in a known metric coordinate
frame and derives PTR-style bearing-distance courses. Output is deterministic:
the ring is ordered clockwise, the start point is chosen lexicographically,
distances are rounded to the requested decimal places, and bearings are rounded
to the nearest whole second. The result is a computational candidate, not
documentary truth, and it does not invent `tie_point`, `tie_line`,
`declared_area`, or provenance.

## Exports

- `to_geojson(parcel)` returns a GeoJSON Feature dictionary.
- `to_wkt(parcel)` returns WKT Polygon text.

Exports are derived interchange geometry. Local exports do not include or invent
a CRS.

## Georeferencing

- `georeference(parcel, tie_point=Point(...), crs="...")` returns a separate
  `GeoreferencedParcel`.

The caller must supply control coordinates and a CRS string, and the PTR record
must contain `tie_line`. PTR Core never guesses EPSG:4326, UTM, PRS92, or any
other CRS.

## Exceptions

- `PTRError`: base class for PTR Core runtime/API exceptions.
- `PTRParseError`: invalid parse/load operation.
- `PTRUnsupportedVersionError`: unsupported `ptr_version`.
- `PTRSerializationError`: unsafe serialization failure.
- `BearingError`: invalid or ambiguous bearing input.
- `GeoreferencingError`: missing explicit georeferencing inputs.

Validation, closure, self-intersection, area difference, and similar parcel QA
conditions are reported as diagnostics/findings rather than exceptions.

## Stability

PTR Core `0.x` is pre-stable. The v0.1 public API is intended to remain usable
through compatible `0.1.x` releases, but future minor `0.x` releases may refine
names or return objects before a stable `1.0`.
