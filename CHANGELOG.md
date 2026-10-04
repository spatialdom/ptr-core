# Changelog

## 0.1.1 - 2026-10-05

- Accept explicit cardinal words and Due bearings in normalized input (#23);
  stored PTR v0.1 syntax remains strict. Expose stable bearing error codes.
- Add shared technical-description and manual-course parsing, source-associated
  partial rows, tie/destination/continuation semantics, and migration fixtures
  (#22). Reject malformed grouping and OCR repairs explicitly.
- Add CandidateParcel 0.2 and manual/structured intake, preserving source
  evidence and diagnostics outside PTR. Conflicts and incomplete extraction
  cannot produce a record; geometric QA remains separate (#19).
- Reject nonfinite distances and stated areas during PTR validation.
- Add public generated-description and editable-table formatting without
  rounding, reordering, geometry computation, or inferred closure (#24).
  Preserve full metadata in structured projections and report prose omissions;
  test parser/intake and extractor-fixture round trips.

## 0.1.0 - 2026-09-07

Initial usable PTR Core release for PTR specification v0.1.

Implemented:

- Python package foundation with `ptr_core` namespace.
- Immutable PTR documentary models.
- Strict PTR v0.1 loading from path, text, and mapping input.
- Canonical JSON serialization.
- Bearing parsing, canonical normalization, and computational azimuths.
- Layered validation diagnostics.
- Local Cartesian reconstruction, course vectors, closure, perimeter, and area.
- Structured QA reports.
- GeoJSON and WKT export for derived parcel geometry.
- Explicit tie-point georeferencing with caller-supplied CRS.
- Parcel-to-parcel comparison primitives with explicit tolerances.
- Parcel topology primitives for overlap, containment, adjacency, shared
  boundary length, gaps, and equivalent geometry checks.
- Explicit geometry transforms for translation, rotation, and CRS conversion.
- Geometry-to-PTR-course derivation for simple metric polygons.
- Unit and vendored PTR v0.1 conformance tests.

Known limitations:

- PTR Core v0.1 supports only PTR specification `0.1`.
- Local reconstruction is planar and metre-based; no CRS is assumed.
- GeoJSON/WKT exports are derived geometry, not authoritative PTR records.
- Geometric QA is intentionally conservative and does not adjust source courses.
