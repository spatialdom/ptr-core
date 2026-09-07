# PTR Core

PTR Core is the reference Python engine for Parcel Truth Records (PTR). PTR
defines the parcel record language; PTR Core implements deterministic parsing,
normalization, validation, and later parcel computation for that language.

Status: early development, PTR v0.1 baseline.

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
from ptr_core import dumps_ptr, load_ptr, parse_bearing, validate

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

assert validate(record).conforms
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
- layered validation diagnostics for serialization, structural, and semantic
  conformance;
- local Cartesian course-vector conversion, traverse reconstruction, closure,
  perimeter, area, declared-area comparison, and geometric QA findings;
- CI for tests, linting, and type checking.

Exports and georeferencing are planned follow-on layers. PTR Core does not
silently alter documentary courses to force geometric closure.

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

Licensing is not finalized for the first public release. See `LICENSE`.
