# Synthetic migration fixtures

Copied unchanged from `spatialdom/ptr-extract` revision
`2333183739d6fcb7bc712b0215b8c5f21f65a0ab`:

- `tests/fixtures/legacy/documentary-cases.json`
- `tests/fixtures/legacy/legacy-observations.json`

These are newly authored synthetic examples and frozen observations of Parcel
Plotter parser v3, not production documents or its private text corpus.
The upstream inventory is `docs/legacy-parser-migration.md`. Core regression
tests compare supported course/tie semantics and explicitly reject malformed
grouping, leading-zero degrees, zero-offset quadrants and noisy OCR anchors.
Worded documentary area extraction stays with PTR Extract; Core accepts numeric
square-metre clauses and retains unsupported clauses for review.

The maintainer approved public distribution of these synthetic copies within
MIT-licensed PTR Core on 2026-10-07, after the release-preparation PR is merged.
This does not change PTR Extract's visibility or license its other contents.
