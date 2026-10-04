# CandidateParcel 0.2 fixtures

`candidate-parcel-v0.2.json` is copied unchanged from
`spatialdom/ptr-extract/tests/fixtures/contracts` at revision
`2333183739d6fcb7bc712b0215b8c5f21f65a0ab`.

`extract-text-v0.2.json` is the actual `extract_text(...).to_dict()` output from
that checkout for a fresh synthetic square, Due West tie, and worded area with
matching parenthesized digits. It freezes the extractor's real per-thence
candidate shape. Tests derive complete, partial, conflicting, assembled
single/multi-page, optional metadata, and failed continuation cases from these
snapshots. Tests and library runtime do not import PTR Extract or OCR packages.
