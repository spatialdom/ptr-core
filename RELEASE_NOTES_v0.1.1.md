# PTR Core v0.1.1

Reference Python implementation for PTR specification **0.1**, Python **3.11+**.
Library version and `ptr_version` are independent. Base installation has no
runtime dependencies; `geospatial` opts into Shapely/GEOS and pyproj/PROJ.

This release includes deterministic bearing/course/technical-description
parsing, neutral text/manual/structured parcel intake, partial evidence,
validation, local geometry/metrics and QA, generated descriptions, editable
tables, GeoJSON/WKT, explicit tie-point georeferencing and optional GIS tools.

The public reference implementation has no document/OCR/model/application
dependency. PTR defines the format, PTR Core implements parcel semantics,
private producers adapt into Core, and applications own product workflows.

Compatibility changes for earlier development-commit consumers:

- Adapt external extraction contracts to `ParcelInput` before calling
  `intake_parcel`. `intake_candidate` is deprecated and accepts neutral inputs
  only; the former `CandidateMapping` protocol is removed.
- Prefer `to_technical_description`; `format_technical_description` remains an
  exact compatibility alias. `is_valid` checks PTR conformance, with detailed
  diagnostics still available through `validate`.
- Install the `geospatial` extra for topology, polygon-to-course conversion and
  CRS transforms. Existing public imports remain available in the base install.

Install the reviewed wheel attached to this GitHub release:

```bash
python -m pip install "https://github.com/spatialdom/ptr-core/releases/download/v0.1.1/ptr_core-0.1.1-py3-none-any.whl"
# GIS consumers:
python -m pip install "ptr-core[geospatial] @ https://github.com/spatialdom/ptr-core/releases/download/v0.1.1/ptr_core-0.1.1-py3-none-any.whl"
```

`SHA256SUMS` accompanies the wheel and source distribution. PyPI publication is
separate and must not be claimed until the approved publisher is configured and
the indexed package is verified. See `docs/RELEASING.md` for release gates and
Parcel Plotter #178 coordination; `docs/MIGRATION.md` describes input migration.

Implementation license: MIT. Vendored PTR conformance materials: CC BY 4.0,
attributed in `THIRD_PARTY_NOTICES.md`. The maintainer has approved public publication after the release-preparation
PR is merged; follow the publication sequence in the release checklist.
