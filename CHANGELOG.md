# Changelog

## Unreleased

- Add versioned synthetic technical-description benchmark `td-v1.0.0` (#21),
  with explicit normalized rows, metadata, ambiguity and diagnostic expectations.
  Report exact recovery, case status, syntax-family failures and version/commit
  identity; compare fixed-corpus reports to expose regressions. CI runs a
  representative subset and uploads reports; tests cover the full corpus and
  benchmark failure/comparison behavior. Exclude document/model evaluation and
  prohibit unapproved private inputs.

- Make Shapely and pyproj optional through `ptr-core[geospatial]` (#27). Base
  parsing, validation, local computation, exports, comparison and rigid transforms
  remain dependency-free. Load backends only at advanced call sites and report
  missing extras through `MissingOptionalDependencyError`.
- Group optional implementations in `ptr_core.geospatial` with compatibility
  imports; test base and geospatial profiles in CI. Update Parcel Plotter's
  dependency declaration to request the extra while retaining its reviewed pin.

- Review and classify the public API into core and advanced capabilities (#28).
  Add `to_technical_description` as the preferred generated-prose name, retaining
  `format_technical_description` as an exact compatibility alias. Add `is_valid`
  for boolean PTR conformance while preserving detailed `validate` diagnostics.
  Retain existing geometry, metric, export, and loading names; document the
  metric-helper decision and Parcel Plotter compatibility.

- Decouple parcel intake from extraction contracts (#26). `ParcelInput` accepts
  caller diagnostics and preserves opaque evidence; Core no longer validates
  source bundles, extraction statuses, provenance, or warning codes.
- Retain `intake_candidate` as a deprecated neutral-intake alias. Schema-specific
  inputs and the `CandidateMapping` protocol are removed; external integrations
  must adapt inputs to `ParcelInput`. See `docs/MIGRATION.md`.
- Replace extraction-contract tests with neutral intake regression coverage for
  partial rows, metadata conflicts, source copying, and adapter error handoffs.

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
