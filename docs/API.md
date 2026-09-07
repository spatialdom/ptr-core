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
