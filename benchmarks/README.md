# Deterministic technical-description benchmark

This repository tool evaluates recovered text → PTR Core parcel interpretation
and normalization. It uses `parse_technical_description` and neutral
`intake_parcel`; it does not open documents or evaluate OCR, layout recognition,
models, confidence, product corrections, or latency. No geospatial extra is
needed. Run from the repository root after installing Core.

```bash
python -m benchmarks.technical_description --output .benchmark-results/baseline.json
python -m benchmarks.technical_description --subset ci --output .benchmark-results/ci.json
python -m benchmarks.technical_description --baseline .benchmark-results/baseline.json --output .benchmark-results/current.json
```

The default corpus is [td-v1/corpus.json](corpora/td-v1/corpus.json), version
`td-v1.0.0`: 25 cases, with a fixed CI selection covering every syntax family.
All text is newly authored synthetic material released under the repository's
MIT license. Expectations are explicit and reviewed independently of actual
parser output; the runner never generates or updates expected answers.

## Expected outputs and metrics

Each case identifies its syntax family, exact input string, CI selection, and:

- ordered normalized `[bearing, distance]` courses, including `null` failed rows;
- destination labels, return indicators, tie courses, reference readings and
  numeric stated-area readings;
- parser completeness, whether neutral intake creates a record, and status;
- exact parser and intake diagnostic code sets.

Status is `complete` when neutral intake creates a record, `partial` when it
cannot but at least one boundary course is recovered, and `rejected` when no
boundary course is recovered. This is a benchmark classification, not a new
library status API. `parser_complete` is reported separately: conflicting
optional metadata can prevent intake even when all boundary courses parse.
Recovered text artifacts and ambiguous directions must remain unresolved;
neither number repair nor selection of conflicting metadata earns a pass.

Reports contain exact field mismatches for each case, total and per-family
complete/partial/rejected counts, and:

- supported-course recovery: exactly matching courses at their expected row
  positions divided by all expected supported courses;
- diagnostic-category accuracy: cases whose parser **and** intake code sets
  match exactly divided by all selected cases;
- case pass counts: all expected fields must match, including failed-row
  positions and absence of unexpected courses or metadata.

Course comparison uses exact normalized numeric values without tolerances.
The recovery rate alone cannot establish a pass: unexpected extra courses or
unsafe acceptance are caught by the complete case comparison. Repeated instances
of the same diagnostic code count as one category. Diagnostic messages and
offset paths are not category metrics; existing parser tests cover source spans.

## Reproducibility and comparisons

Report schema version 1 includes the imported Core package version, its Git
commit and dirty-worktree flag when it is tracked source, Python version, corpus
version, canonical SHA-256, subset, per-case observations and family summaries.
Installed wheels have no Git identity, so commit/dirty are explicitly `null`.
The hash covers canonical JSON content, including expectations and subset flags;
JSON formatting and checkout line endings do not affect it. Reports contain no
timestamps, so repeated runs in the same environment are deterministic.

For comparisons, keep the runner and corpus fixed and change the Core checkout
or installation under test. For example, set `PYTHONPATH` to another reviewed
checkout's `src` directory before running the same command (in PowerShell use
`$env:PYTHONPATH = 'C:/path/to/older/ptr-core/src'`). The selected checkout must
expose both benchmarked entry points. The report identifies the imported Core
checkout rather than assuming the runner's commit is its version.

`--baseline` reports passed→failed regressions, failed→passed improvements, and
changed observations by case ID, plus the baseline Core identity. It requires
the same corpus hash/version and subset; comparing changed expectations would
hide regressions. Preserve old corpus versions. Add or change cases/expectations
only in a new documented corpus revision, with a reason for intentional grammar
changes. Never overwrite expectations merely to make a failing run pass.

Exit status is 0 for all expectations passing, 1 for any mismatch, and 2 for
invalid corpus/baseline input. Established supported-grammar regressions block a
release unless intentionally changed, reviewed, documented, and versioned.
CI runs the representative subset in both installation profiles and retains
JSON reports as artifacts even when the benchmark fails. Pytest also runs the
full corpus and exercises metric/regression reporting.

## Rights and privacy

The shipped corpus and loader are synthetic-only. Do not copy private titles,
survey descriptions, customer submissions, photographs, OCR outputs, personal
data, or a private application corpus into this benchmark, even if described as
anonymized. A non-synthetic future corpus requires approved redistribution rights
and privacy review, documented provenance/license, and a separate corpus policy
revision; it cannot be enabled by labelling private text as synthetic.

Synthetic references and measurements convey no cadastral or legal truth.
Selected OCR-like text artifacts are hand-authored strings for parser robustness;
they do not measure any OCR engine. The report has no product correction count,
character error rate, learned-model metric, or model timing.
