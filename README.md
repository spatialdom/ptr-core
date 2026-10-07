# PTR Core

PTR Core is the reference Python engine for Parcel Truth Records (PTR). PTR
defines the parcel record language; PTR Core implements deterministic parsing,
normalization, validation, and parcel computation for that language.

Status: PTR Core v0.1.1 for PTR specification v0.1. Intake accepts generic
parcel text and structured readings with opaque source references.

PTR Core is designed as a reusable library for Parcel Plotter, PTR Studio, QGIS
integrations, SPARTA, Survey Kit, APIs, CLIs, and tests. It has no Django, web
framework, database, or UI dependency.

## Install

From this repository:

```bash
python -m pip install -e .
```

For development:

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
mypy
```

## Quick Start

```python
from ptr_core import dumps_ptr, is_valid, load_ptr, parse_bearing, validate

record = load_ptr(
    """
    {
      "ptr_version": "0.1",
      "lines": [
        ["N", 10.0],
        ["E", 10.0],
        ["S45-00W", 14.1421356237]
      ]
    }
    """
)

assert is_valid(record)
assert validate(record).conforms  # detailed diagnostics remain available
assert parse_bearing("N 68 deg 28' E").canonical == "N68-28E"
print(dumps_ptr(record))
```

## Current Scope

Implemented foundation:

- modern `pyproject.toml` package using the `ptr_core` import namespace;
- immutable documentary domain models for `PTRRecord` and `Course`;
- loading from file paths, JSON text, and Python mappings;
- canonical JSON serialization;
- PTR v0.1 bearing parsing and safe normalization;
- shared technical-description/manual-course parsing with ordered partial rows;
- generic parcel intake preserving evidence and caller diagnostics outside PTR;
- generated readable descriptions and editable table projections of records;
- layered validation diagnostics for serialization, structural, and semantic
  conformance;
- local Cartesian course-vector conversion, traverse reconstruction, closure,
  perimeter, area, declared-area comparison, and geometric QA findings;
- structured QA reports, GeoJSON/WKT export, and explicit tie-point
  georeferencing;
- vendored PTR v0.1 conformance corpus tests;
- CI for tests, linting, and type checking.

PTR Core does not silently alter documentary courses to force geometric closure.
It contains no application-specific UI, database, cloud, OCR, ownership,
taxation, zoning, or other contextual logic.

## Public API

The v0.1 public API is exported from `ptr_core`; applications should not need to
import internal modules. See `docs/API.md` for the entry points, return objects,
exception hierarchy, core/advanced inventory, and `0.x` stability expectations.
`is_valid` checks PTR conformance; geometry QA remains separate. Generated prose
uses `to_technical_description`; `format_technical_description` remains an exact
compatibility alias for existing integrations.

PTR Core currently supports PTR specification versions:

```python
from ptr_core import SUPPORTED_PTR_VERSIONS

assert SUPPORTED_PTR_VERSIONS == ("0.1",)
```

## Geometry

Derived geometry uses a local Cartesian frame only: X/Easting is positive east
and Y/Northing is positive north, both in metres. The origin `(0, 0)` is a
computational convenience for Point 1, not a coordinate reference system.

```python
from ptr_core import load_ptr, reconstruct

record = load_ptr("lot.ptr")
parcel = reconstruct(record)

print(parcel.vertices)
print(parcel.final_endpoint)
print(parcel.metrics.closure.linear)
print(parcel.metrics.area)
```

Area is computed with the shoelace formula over the reconstructed path and an
implicit closing segment back to Point 1. Misclosure is reported separately; the
traverse is not snapped, adjusted, balanced, or redistributed.

## QA, Export, And Georeferencing

```python
from ptr_core import Point, georeference, qa_report, to_geojson, to_wkt

report = qa_report(record).to_mapping()

local_feature = to_geojson(parcel)
local_wkt = to_wkt(parcel)

referenced = georeference(
    parcel,
    tie_point=Point(500000.0, 1600000.0),
    crs="EPSG:32651",
)
referenced_feature = to_geojson(referenced)
```

QA reports combine validation, metrics, and geometric findings while keeping
documentary validity separate from derived QA warnings. GeoJSON and WKT exports
are derived interchange outputs, not replacements for `.ptr`.

Local exports do not include or invent a CRS. Referenced exports require caller
supplied control coordinates, a PTR `tie_line`, and an explicit CRS identifier.

Numerical tolerances default to `1e-9` metres for closure and `1e-9` square
metres for area QA classification. These tolerances classify derived QA
findings only; they do not alter documentary measurements.

## Comparison

```python
from ptr_core import compare_parcels

comparison = compare_parcels(
    parcel_a,
    parcel_b,
    distance_tolerance=0.01,
    area_tolerance=0.01,
)
```

Comparison results expose documentary equality, course differences, area and
perimeter deltas, centroid translation, vertex/boundary distance metrics, and
frame compatibility. They provide evidence for applications; they do not decide
legal identity or cadastral correctness.

## Topology

```python
from ptr_core import analyze_topology

topology = analyze_topology(
    parcel_a,
    parcel_b,
    distance_tolerance=0.01,
    area_tolerance=0.01,
)
```

Topology results expose compatible-frame status, overlap area, containment,
point-touching, shared-edge adjacency, shared-boundary length, and gap distance.
PTR Core uses Shapely/GEOS behind this API for polygon topology; tolerances are
explicit and no parcel geometry is automatically snapped or repaired.

## Transforms

```python
from ptr_core import Point, rotate, transform_crs, translate

moved = translate(parcel, dx=10.0, dy=0.0)
rotated = rotate(parcel, angle_degrees=90.0, origin=Point(0.0, 0.0))
projected = transform_crs(
    referenced,
    source_crs="EPSG:4326",
    target_crs="EPSG:3857",
)
```

Translation and rotation are local rigid-body transforms. CRS transforms require
explicit source and target CRS identifiers. Each transform returns a separate
derived geometry object with reproducible metadata and leaves the source PTR
record unchanged.

## Geometry To Courses

```python
from ptr_core import derive_courses_from_polygon

candidate = derive_courses_from_polygon(
    [(0.0, 0.0), (0.0, 10.0), (20.0, 10.0), (20.0, 0.0)],
    coordinate_frame="local-metres",
    distance_decimals=3,
)
ptr_like = candidate.to_mapping()
```

Geometry-to-course conversion accepts simple polygons in a known metric
coordinate frame. It emits clockwise canonical PTR bearings, rounds distances to
the requested decimal places, and rounds bearings to the nearest second. The
output is a computational PTR candidate, not documentary truth.

## Text, Parcel Intake, And Review Formatting

```python
from ptr_core import (
    to_technical_description,
    intake_parcel,
    parse_technical_description,
    project_manual_table,
)

text = """thence Due North, 10 m; thence East, 10 m;
thence South, 10 m; thence West, 10 m;"""
parsed = parse_technical_description(text)
assert parsed.complete
result = intake_parcel(text)
assert result.record is not None
generated = to_technical_description(result.record)
table = project_manual_table(result.record).to_mapping()
print(generated.text)
```

`intake_parcel(ParcelInput(...))` also accepts structured courses, tie/reference
readings, stated area, names, and record IDs. Opaque `sources` and `context`
survive interpretation without being validated as an external schema. Caller
`diagnostics` can block incomplete or unresolved input while retaining partial
rows and unparsed text. A conforming record can still have geometry QA warnings.
External services and applications adapt their own contracts into `ParcelInput`.

Generated descriptions preserve course order and numeric values without
asserting closure or authentic source wording. `generated.omitted_fields`
identifies metadata that prose excludes; the table keeps metadata and unknown
extensions separately and can produce a lossless `to_ptr_mapping()`.

See [docs/API.md](docs/API.md) for supported grammar, typed outputs, diagnostics,
and the neutral intake contract. See [docs/MIGRATION.md](docs/MIGRATION.md)
for downstream adapter guidance and migration from the deprecated intake name.
The APIs do not read source documents or overwrite transcriptions.

## PTR v0.1 Input

```json
{
  "ptr_version": "0.1",
  "name": "Lot 2173",
  "record_id": "cad-123-lot-2173",
  "tie_point": "BLLM No. 1, Cad-123",
  "tie_line": ["S11-44W", 2351.0],
  "lines": [
    ["N", 100.0],
    ["E", 80.0],
    ["S", 100.0],
    ["W", 80.0]
  ],
  "declared_area": 8000.0
}
```

Normative field definitions live in the PTR specification repository:
<https://github.com/spatialdom/ptr>.

## Validation Model

PTR Core distinguishes:

1. serialization: valid UTF-8 JSON with one top-level object;
2. structural conformance: required fields, field types, array shapes, and
   version value;
3. semantic conformance: canonical bearings, positive metre distances, positive
   declared area, and field relationships;
4. geometric QA: derived diagnostics such as closure, orientation, and
   self-intersection.

A record with serialization, structural, or semantic errors is not conforming.
Geometric QA findings are reported separately and do not by themselves rewrite
or invalidate documentary source truth.

## License

PTR Core is released under the MIT License. See `LICENSE`.
