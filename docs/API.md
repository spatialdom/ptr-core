# PTR Core v0.1 Public API

PTR Core v0.1 exposes normal application entry points from `ptr_core`. Downstream
applications should not need to import internal modules.

## Public Surface Inventory

Core entry points cover the common record workflow. Advanced exports support
explicit control, derived spatial operations, or inspection of typed results.
Both groups are supported from `ptr_core`; this classification does not change
imports or stability. Compatibility names remain available separately.

| Class | Capability | Public exports |
| --- | --- | --- |
| Core | Read and write records | `load_ptr`, `dumps_ptr`, `dump_ptr` |
| Core | Interpret parcel readings | `intake_parcel`, `ParcelInput`, `IntakeResult` |
| Core | Normalize and parse | `parse_bearing`, `parse_course`, `parse_technical_description` |
| Core | Check conformance and QA | `validate`, `is_valid`, `qa_report` |
| Core | Derive local geometry and metrics | `reconstruct`, `compute_metrics` |
| Core | Generate prose and editable rows | `to_technical_description`, `project_manual_table` |
| Core | Export derived geometry | `to_geojson`, `to_wkt` |
| Core | Record and diagnostic types | `PTRRecord`, `Course`, `Bearing`, `Diagnostic`, `Severity`, `ValidationResult` |
| Advanced | Explicit loading and numeric/vector parsing | `load_ptr_text`, `load_ptr_mapping`, `parse_distance`, `course_to_vector` |
| Advanced | Spatial operations | `georeference`, `compare_parcels`, `analyze_topology`, `translate`, `rotate`, `transform_crs`, `derive_courses_from_polygon` |
| Advanced | Interpretation and formatting results | `ParsedCourse`, `ParsedValue`, `SourceSpan`, `TechnicalDescriptionResult`, `GeneratedDescription`, `CourseRow`, `ManualTableProjection` |
| Advanced | Geometry and metric results | `Point`, `Vector`, `DerivedParcel`, `ParcelMetrics`, `Closure`, `AreaComparison`, `GeoreferencedParcel`, `TransformedParcel`, `TransformStep`, `PTRCourseCandidate` |
| Advanced | Comparison and topology results | `BoundingBox`, `CourseComparison`, `ComparisonResult`, `TopologyResult`, `QAReport` |
| Advanced | Exceptions | `PTRError`, `PTRParseError`, `PTRSerializationError`, `PTRUnsupportedVersionError`, `BearingError`, `CourseParseError`, `PTRFormattingError`, `GeoreferencingError`, `TransformError`, `GeometryToCoursesError` |
| Compatibility | Earlier prose-generation name | `format_technical_description` (exact alias of `to_technical_description`) |
| Deprecated | Earlier intake name | `intake_candidate` (neutral input only; see migration guide) |

`SUPPORTED_PTR_VERSIONS` and `__version__` describe format support and package
version respectively. Every other supported package export appears above.

The naming review retains `validate`, `reconstruct`, `compute_metrics`, the
GeoJSON/WKT exports, and Python's conventional load/dump names. `reconstruct`
specifically derives an unadjusted local traverse from documentary courses;
`compute_metrics` exposes a coherent result with units and closure components.
Standalone `compute_area`, `compute_perimeter`, and `compute_misclosure` helpers
are deliberately omitted: they would duplicate result fields and leave unclear
whether inputs were records or geometry, and whether misclosure meant a vector,
a length, or a ratio. Use `parcel.metrics.area` (square metres), `.perimeter`
(metres), and `.closure` (`east`, `north`, `linear` in metres).

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
area interpretation belongs to the caller. All alternatives remain available.

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
`TechnicalDescriptionResult.to_mapping()` includes partial boundary rows,
separate ties/values, raw unparsed spans, and diagnostics for neutral review
handoffs. `IntakeResult.to_mapping()` includes these description mappings too.

## Parcel Intake

- `intake_parcel(text_or_ParcelInput)` returns `IntakeResult` for text, manual,
  and structured readings. Inputs must be text or `ParcelInput`; external
  mappings/objects require a caller-owned adapter.
- `ParcelInput` accepts `text`, `courses`, `tie_point`, `tie_line`,
  `declared_area`, `name`, `record_id`, `reviewed`, `sources`, `context`, and
  `diagnostics`. Structured courses may be `Course`, `[bearing, distance]`, or
  mappings with `bearing` and `distance` (also `distance_m`), plus optional
  `raw_text`, `candidate_id` (an opaque row label), `sources`,
  `destination_point`, and `returns_to_beginning`.
- `tie_line` accepts a structured course or supported text containing exactly
  one tie course. `declared_area` accepts a positive finite number or supported
  numeric string in square metres. Core does not infer or convert area units.

All readings share deterministic parsing and normalization. Different text and
structured courses produce `conflicting_courses`; disagreeing explicit and text
reference/tie/area readings produce `conflicting_values`. Missing optional
metadata allows local records, but a tie line requires a reference. Core never
selects competing alternatives, assembles fragments, infers continuation, or
uses opaque evidence to determine conformance.

`ParcelInput.diagnostics` is a tuple of `Diagnostic` objects supplied by the
caller. Any `Severity.ERROR` blocks record creation even when recovered courses
are valid. Warnings and informational diagnostics are retained without blocking.
Core does not interpret caller codes or layers. `reviewed` is retained as caller
state and never overrides errors.

`IntakeResult.record` is a conforming `PTRRecord` or `None`. Ordered `rows`,
`descriptions` (including ties, values and unparsed spans), `diagnostics`,
`evidence`, and `reviewed` remain outside PTR. `evidence` retains all supplied
readings, `sources`, `context`, caller diagnostics, and review state with copied
nested mappings. Sources are opaque mapping sequences: Core copies their contents
without resolving IDs or validating any document or service contract. Text rows
retain source associations; structured rows can supply their own sources. Row
spans refer to retained row text, while parsed text spans use exact input offsets.
When both text and courses are supplied, returned rows use text spans and the
structured representation remains in evidence.

`to_mapping()` creates a review handoff with separately copied evidence and
source spans. Use JSON-compatible opaque evidence when a JSON handoff is needed.
No new PTR fields are created for sources, destinations, diagnostics, or review.

Stable intake codes include `invalid_source_reference`, `conflicting_values`,
`conflicting_courses`, `invalid_destination`, `invalid_tie_line`, and
`invalid_stated_area`, alongside parser and PTR validation codes. Caller
codes pass through unchanged.

```python
from ptr_core import Diagnostic, ParcelInput, intake_parcel, qa_report

manual = intake_parcel(ParcelInput(
    courses=(["Due North", "10"], ["East", 10], ["South", 10], ["West", 10]),
    sources=({"reference": "opaque:survey-1"},),
    reviewed=True,
))
assert manual.record is not None
report = qa_report(manual.record)

partial = intake_parcel(ParcelInput(
    text="thence North, 10 m; thence East, 10 m; thence South, 10 m;",
    diagnostics=(Diagnostic("adapter", "incomplete_input", "More input is needed."),),
    context={"alternatives": ["unresolved reading"]},
))
assert partial.record is None
assert len(partial.rows) == 3
```

The deprecated `intake_candidate` name is a warning-emitting alias for neutral
intake only. See [migration and external adapters](MIGRATION.md) before upgrading
an integration that used schema-specific intake. Supported PTR remains `0.1`.

## Generated Description And Editable Table

- `to_technical_description(record)` is the preferred generation name.
  `format_technical_description` remains an exact compatibility alias with the
  same signature, result, and exceptions, without a deprecation warning. It
  returns `GeneratedDescription` with `text`, `omitted_fields`, and warning
  `diagnostics`. The text identifies itself
  as generated and preserves boundary order, cardinals, quadrants, seconds,
  numeric distances, tie point/tie line, and numeric stated area. It performs no
  geometry computation and never infers a return to the point of beginning.
  Numeric values use Python's round-trip representation without extra rounding.
- `project_manual_table(record)` returns `ManualTableProjection`: ordered
  canonical `CourseRow` values, supporting `metadata`, and unknown `extensions`
  separately. `to_mapping()` returns library-neutral editable row dictionaries;
  `to_ptr_mapping()` preserves the full record, including extension values.
- `PTRFormattingError.diagnostics` explains invalid records or unsafe
  serialization. Its parent is `PTRParseError`.

Prose deliberately omits `name`, `record_id`, and extensions, reporting their
paths in `omitted_fields` and `metadata_not_in_prose`. The structured projection
preserves them. Destination labels and return wording are not stored in PTR and
cannot be recovered from a record. Decimal spelling and trailing zeroes from
original text are also not stored by PTRRecord's numeric values. These APIs
preserve represented values, not original spelling, source transcripts,
signatures, or certification.

Reference strings use JSON quoting, so semicolons, quotation marks, line breaks,
Unicode, and words such as `thence` within reference metadata survive parsing.
The generated text round-trips through `parse_technical_description` and
`intake_parcel` for supported boundary/reference/tie/area semantics. Use the
table's `to_ptr_mapping()` when retaining names, record IDs, and extensions.
Projection does not add fields to PTR or write source documents.

```python
from ptr_core import (
    to_technical_description, intake_parcel, load_ptr_mapping,
    project_manual_table,
)

# record is an existing conforming PTRRecord.
generated = to_technical_description(record)
round_trip = intake_parcel(generated.text)
assert round_trip.record.lines == record.lines
assert round_trip.record.tie_line == record.tie_line
table = project_manual_table(record)
assert load_ptr_mapping(table.to_ptr_mapping()) == record
```

## Validation And QA

- `validate(source)` returns `ValidationResult`; expected conformance failures
  are diagnostics, not exceptions.
- `is_valid(source)` returns `validate(source).conforms` as a boolean for the
  same JSON-text, mapping, and record inputs. It checks strict PTR serialization,
  structural, and semantic conformance; it does not assert geometric closure,
  source authenticity, or legal/cadastral validity. Use `validate` when the
  caller needs the reasons for rejection.
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
- `CourseParseError`: invalid manual course/distance input, with a stable `code`.
- `PTRFormattingError`: invalid record projection, with structured `diagnostics`.
- `GeoreferencingError`: missing explicit georeferencing inputs.

Validation, closure, self-intersection, area difference, and similar parcel QA
conditions are reported as diagnostics/findings rather than exceptions.

## Stability

PTR Core `0.x` is pre-stable. The v0.1 public API is intended to remain usable
through compatible `0.1.x` releases, but future minor `0.x` releases may refine
names or return objects before a stable `1.0`.

## Paste compatibility and source precision

`ParsedCourse.distance_text` retains the readable distance lexeme (grouping
commas removed) separately from the numeric course. Source spans remain exact
offsets in the original input. Consumers can retain trailing zeroes and precision
without scanning source grammar themselves. Structured rows may leave this
field unset; the numeric course remains authoritative.

The generic TD parser supports integer number-word areas, explicit parenthesized
numeric stated areas, and numeric square-decimetre documentary wrappers. Written
and numeric area contradictions retain both values and block intake. A beginning
point marker without a `being ... from ...` tie course is informational context.
Core still rejects malformed grouping, leading-zero bearing degrees and OCR
anchor/character repairs. Unsuccessful readings and their source spans survive
for explicit review. No CandidateParcel knowledge is introduced.
