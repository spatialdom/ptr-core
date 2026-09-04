# PTR Core

**PTR Core is the reference computational engine for Parcel Truth Records (PTR).**

PTR defines the parcel language. PTR Core implements the parcel behavior.

> `.ptr` says what a parcel record contains.  
> PTR Core says how that record is parsed, validated, reconstructed, computed, checked, transformed, compared, and exported.

This repository is the home of the reusable parcel-domain logic shared by Spatialdom applications such as Parcel Plotter, PTR Studio, QGIS integrations, SPARTA, Survey Kit, and future parcel services.

## Status

**Early development / PTR v0.1 baseline.**

The current objective is to build a small, deterministic, well-tested reference implementation against the evolving PTR v0.1 specification in [`spatialdom/ptr`](https://github.com/spatialdom/ptr).

PTR Core should follow the standard; it should not silently redefine it.

## Relationship to the PTR ecosystem

```text
Land title / technical description
            ↓
          .PTR
            ↓
        PTR Core
            ↓
  derived parcel object
  geometry · vertices · area
  perimeter · closure · QA
            ↓
       applications
  Parcel Plotter · PTR Studio
  QGIS · SPARTA · Survey Kit
            ↓
     contextual linkages
 hazards · zoning · valuation
 buildings · roads · imagery
```

The responsibilities are intentionally separated:

| Repository / layer | Responsibility |
|---|---|
| `spatialdom/ptr` | PTR specification, schema, examples, conformance fixtures, governance |
| `spatialdom/ptr-core` | Parsing, validation, parcel computation, QA, transforms, comparison, topology primitives, exports |
| Applications | UI, projects, persistence, collaboration, workflows, institutional logic |
| Contextual datasets | Hazards, zoning, buildings, valuation, roads, imagery, taxation, ownership, and other external information |

## Design principles

### 1. Standard first

PTR Core implements the PTR specification. Format changes belong in `spatialdom/ptr` before they are assumed here.

### 2. Preserve documentary truth

PTR Core may normalize safe representations for computation, but it must not silently invent or alter survey measurements to force a parcel to close.

A non-closing technical description can still be a valid documentary record and should produce a geometric QA result rather than an automatically corrected parcel.

### 3. Derived values stay derived

Geometry, vertices, area, perimeter, closure, centroid, bounding boxes, and similar values are computed from the PTR record. They do not become authoritative PTR fields merely because PTR Core can calculate them.

### 4. No hidden coordinate assumptions

A PTR can exist without coordinates. Local reconstruction should therefore work in a local Cartesian frame.

Georeferencing is a separate operation and must require sufficient external control information rather than guessing a CRS or tie-point coordinate.

### 5. Parcel-native behavior

PTR Core is not intended to become a generic GIS library. It should expose behavior that makes sense specifically for parcels and survey-derived parcel descriptions.

### 6. Deterministic and reusable

Core operations should be deterministic, testable, UI-independent, database-independent, and suitable for use by web, desktop, mobile, CLI, API, and batch-processing applications.

### 7. Context remains external

Ownership, taxation, zoning, hazards, buildings, valuation, permits, imagery, and similar information do not belong in PTR Core merely because they can be linked to a parcel.

PTR Core may provide geometry and linkage primitives that applications use to perform those joins.

## PTR v0.1 input

A PTR v0.1 record is intentionally small. A representative example is:

```json
{
  "ptr_version": "0.1",
  "name": "Lot 2173",
  "tie_point": "BLLM No. 1, Cad-123",
  "tie_line": ["S11-44W", 2351.00],
  "lines": [
    ["S04-47E", 79.70],
    ["S89-37W", 67.41],
    ["N03-07W", 27.93]
  ],
  "declared_area": 10000.00
}
```

The normative field definitions live in the PTR specification repository.

## Core processing model

```text
PTR JSON / object
      │
      ▼
    Parse
      │
      ▼
  Normalize
      │
      ▼
   Validate
      │
      ▼
Reconstruct traverse
      │
      ▼
Derived parcel object
      │
      ├── vertices
      ├── local geometry
      ├── perimeter
      ├── computed area
      ├── closure vector
      ├── linear misclosure
      ├── QA findings
      └── documentary/computed comparison
      │
      ├── export
      ├── georeference
      ├── compare
      └── topology operations
```

## Planned v0.1 capabilities

The initial core should prioritize a narrow but complete chain from PTR text to a trustworthy derived parcel:

- parse PTR JSON;
- normalize supported bearing inputs;
- validate structural and semantic conformance;
- reconstruct the ordered bearing-distance traverse;
- derive parcel vertices in a local coordinate frame;
- compute perimeter;
- compute area;
- compute closure and misclosure;
- compare documentary and computed metrics;
- produce structured QA findings;
- export derived geometry to interoperable forms such as GeoJSON and WKT;
- optionally georeference a locally reconstructed parcel when explicit external control coordinates are supplied.

Later capabilities can build on the same parcel object:

- compare parcels;
- detect intersection/overlap;
- test containment;
- identify shared boundaries and adjacency;
- transform parcel geometry;
- support subdivision/consolidation primitives;
- process parcel collections through PTRC-aware applications or libraries.

## Proposed public API

The exact Python API is not yet stable, but the intended shape is deliberately small and composable:

```python
from ptr_core import (
    load_ptr,
    validate,
    reconstruct,
    compute_metrics,
    georeference,
    to_geojson,
)

record = load_ptr("lot-2173.ptr")
validation = validate(record)
parcel = reconstruct(record)
metrics = compute_metrics(parcel)
feature = to_geojson(parcel)
```

Lower-level operations should also be available for applications that need them, for example bearing normalization, course conversion, closure calculation, or explicit QA checks.

The public API will be finalized through repository issues and tests rather than treated as stable from this README example.

## Validation philosophy

PTR Core should distinguish different kinds of validity instead of returning one generic pass/fail flag.

A useful working model is:

1. **Serialization** — is it valid UTF-8 JSON?
2. **Structural conformance** — are required PTR fields and value shapes correct?
3. **Semantic conformance** — are bearings, distances, field relationships, and course rules meaningful under the PTR specification?
4. **Geometric QA** — does the reconstructed parcel close, self-intersect, degenerate, or differ materially from its declared area?

A parcel can therefore be structurally valid while still producing important QA warnings.

## Coordinate model

For a PTR with no external coordinates, PTR Core should reconstruct the parcel in a **local Cartesian coordinate frame**. The origin is a computational convenience, not documentary truth and not a claim about real-world location.

When sufficient external control information is supplied, a separate georeferencing operation can place the derived geometry in a real coordinate reference system.

PTR Core must not invent a tie-point coordinate or CRS.

## What PTR Core is not

PTR Core is not:

- the PTR standard itself;
- a cadastral database;
- an ownership or land-registration system;
- a tax-mapping application;
- a user interface;
- a cloud collaboration service;
- an OCR product;
- a general-purpose GIS engine;
- a repository for hazard, zoning, valuation, building, or other contextual data.

Those products may depend on PTR Core, but they belong above it.

## Repository direction

The first development sequence is:

```text
package foundation
      ↓
PTR loading + models
      ↓
bearing normalization
      ↓
validation
      ↓
traverse reconstruction
      ↓
closure + area + perimeter
      ↓
QA report
      ↓
GeoJSON / WKT export
      ↓
explicit georeferencing
      ↓
comparison / topology primitives
```

The issue tracker is the implementation roadmap for this work.

## Version relationship

PTR Core versions and PTR specification versions are related but not identical.

For example, PTR Core `0.x` may support PTR specification `0.1`. The library should explicitly declare which PTR specification versions it can read and write rather than assuming package version equality.

## Testing

Tests should include both PTR Core unit tests and the shared conformance fixtures maintained in `spatialdom/ptr`.

Every real-world parser ambiguity, numerical edge case, and geometry failure that is legally and ethically reusable should eventually become a regression test.

The long-term strength of PTR Core will come less from the number of functions it exposes than from the depth of parcel cases it handles correctly.

## License

Licensing will be finalized before the first public release and should remain compatible with the open PTR standard and broad reuse of the core library.

## Spatialdom

PTR and PTR Core are developed by [Spatialdom](https://github.com/spatialdom) as part of an open parcel infrastructure for creating, validating, exchanging, collecting, analyzing, and connecting land parcels across software and institutions.
