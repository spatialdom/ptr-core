# Neutral intake migration

Core interprets parcel readings. Integrations own their transport contracts,
selection, completeness checks, and external provenance validation. The boundary
is `ParcelInput` → `intake_parcel` → `IntakeResult`; there is no document model
inside Core.

## Migrating the old entry point

Replace `intake_candidate(external_input)` with
`intake_parcel(your_adapter(external_input))`. The deprecated name remains
importable and emits `DeprecationWarning`, but accepts only text or `ParcelInput`.
Passing an external mapping or a `to_dict()` object raises `TypeError` with
migration guidance. The old `CandidateMapping` protocol is removed. This is an
intentional behavior change: the shim cannot safely interpret external schemas
while keeping Core independent. Migrate before upgrading the integration.

Manual/paste callers continue to use `intake_parcel(text)` or
`intake_parcel(ParcelInput(courses=...))` without an adapter.

## PTR Extract adapter

Keep CandidateParcel mapping code in PTR Extract or the consuming integration,
never in `ptr_core`. Validate the producer's schema and source/provenance links
there. Resolve competing, ambiguous, conflicting, and unsupported readings there;
do not select the first alternative or highest confidence automatically.

Map the selected readings as follows:

| Producer reading | Neutral Core field |
| --- | --- |
| Assembled technical-description `raw_text` | `text` |
| Explicit ordered boundary readings | `courses` |
| Selected parcel identifier | `name` (application supplies `record_id`) |
| Selected reference-point text | `tie_point` |
| Selected tie reading | `tie_line` as text or `[bearing, distance]` |
| Selected numeric area in square metres | `declared_area` |
| Source links | `sources`, or per-course `sources` |
| Full original payload, alternatives, producer metadata | `context` |
| Unresolved completeness/selection failures | caller `Diagnostic` errors |

Assemble fragments only when the producer/application has established their
order and completeness. Core receives one text string; it does not sort source
pages or reconstruct source offsets. Keep the original fragments and offsets in
`context`. Core parser offsets refer to the exact assembled text supplied.
Use structured per-course sources when distinct course associations are needed.

Number-word interpretation, documentary-number wrappers, metric unit checks,
source bundle/page validation, extraction status interpretation, and warning
classification belong to this adapter. Missing optional area/reference/tie
readings need not block local records. An unresolved parcel reading, failed
source, or possible missing continuation must become an error diagnostic even
when recovered courses happen to form a valid record. Preserve original warnings
in context; Core does not know which producer warning codes are blocking.

This handoff helper belongs in the integration after its schema-specific
validation and selection. Its arguments are the selected values, not an external
transport object:

```python
from ptr_core import Diagnostic, ParcelInput, intake_parcel


def interpret_selected_readings(
    *, original_payload, assembled_text, ordered_courses=None,
    reference=None, tie=None, area_m2=None, parcel_name=None,
    source_refs=(), blockers=(),
):
    return intake_parcel(ParcelInput(
        text=assembled_text,
        courses=tuple(ordered_courses) if ordered_courses is not None else None,
        tie_point=reference,
        tie_line=tie,
        declared_area=area_m2,
        name=parcel_name,
        sources=tuple(source_refs),
        context={"original_payload": original_payload},
        diagnostics=tuple(
            Diagnostic("adapter", "unresolved_input", message)
            for message in blockers
        ),
    ))
```

For unresolved alternatives, pass the recovered selected/partial text and keep
all alternatives in `original_payload`, with blockers describing unresolved
choices. Never omit a blocker just to obtain a record. Confidence and producer
warnings preserved only in opaque context cannot override parsing or validation.

## Parcel Plotter adapter

The application's import boundary calls its PTR Extract adapter above, stores
`result.to_mapping()` for review, and uses `result.record` only when present.
Retain the original payload/transcription separately. Map manual-table rows
directly to `ParcelInput(courses=...)`; map paste input to `ParcelInput(text=...)`.
Both flows use the same Core parser and preserve failed rows.

```python
from ptr_core import ParcelInput, intake_parcel


def interpret_manual_rows(rows, metadata, source_refs=(), reviewed=False):
    return intake_parcel(ParcelInput(
        courses=tuple(rows),
        tie_point=metadata.get("tie_point"),
        tie_line=metadata.get("tie_line"),
        declared_area=metadata.get("declared_area"),
        name=metadata.get("name"),
        record_id=metadata.get("record_id"),
        sources=tuple(source_refs),
        context={"manual_metadata": metadata},
        reviewed=reviewed,
    ))
```

After an explicit user correction/selection, build a new input with the updated
readings and the remaining blockers. `reviewed=True` never bypasses errors. A
conforming record still needs separate geometry QA, and does not establish legal
or cadastral certainty. These adapter recipes introduce no dependency on an
application, producer library, or document-processing package inside Core.
