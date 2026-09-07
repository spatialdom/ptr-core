# PTR Core v0.1.0 Release Notes

PTR Core v0.1.0 is the first usable Python engine for PTR specification v0.1.

It can load a conforming PTR v0.1 record, validate it, reconstruct local
geometry, compute core metrics, report closure and geometry QA findings, export
derived geometry, and explicitly georeference a parcel when caller-supplied
control information is available.

Release checks:

- Public API reference: `docs/API.md`.
- Supported PTR versions: `SUPPORTED_PTR_VERSIONS = ("0.1",)`.
- License: MIT.
- Test suite: unit tests plus vendored PTR v0.1 conformance corpus.

Tagging convention: create `v0.1.0` after release approval.
