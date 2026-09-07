# Changelog

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
- Unit and vendored PTR v0.1 conformance tests.

Known limitations:

- PTR Core v0.1 supports only PTR specification `0.1`.
- Local reconstruction is planar and metre-based; no CRS is assumed.
- GeoJSON/WKT exports are derived geometry, not authoritative PTR records.
- Geometric QA is intentionally conservative and does not adjust source courses.
