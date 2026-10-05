<!-- GENERATED FILE - do not edit here.
     Source: skills/shared/provenance/SCHEMA.md
     Regenerate: python scripts/sync_shared.py
     A local copy exists so this skill works when its directory is
     installed on its own, in Claude or in Codex. -->

# Provenance ledger schema

Six CSV tables, one validator. Every CLEWs skill points here; none redefines the schema.

**The invariant:** every populated model value resolves to exactly one `MODEL_MAP` row; every
`MODEL_MAP` row carries at least one evidence ID; every referenced ID resolves; every retained
evidence file matches its `sha256`.

**The version-inheritance invariant:** begin every new model version with a complete copy of the
current canonical ledger and all retained evidence. Carry unchanged records forward, add new
records, and supersede changed mappings without deleting their lineage. A previous-version name
may document chronology, but the new version must be independently interpretable and must never
depend on an earlier package or installed case to supply its sources, calculations, assumptions,
mappings, gaps, or evidence files.

Worked examples live in `templates/`. Validate with:

```
python provenance.py LEDGER_DIR [--stage scaffold|build|delivery] [--model-inputs DIR] [--json REPORT]
```

Exit 0 passes, exit 1 fails. `scaffold` checks only that the six files exist with the right
columns. `build` adds every row, reference and digest check. Input coverage — proving every
populated input file is mapped — runs at any stage once `--model-inputs` is given, and
`delivery` additionally requires it. So a wrapper that knows where inputs live, as the
packaged `validate_provenance.py` does, proves coverage from `build` onwards; expect
unmapped-input failures there rather than only at `delivery`.

## ID conventions

`SRC_` sources, `CALC_` calculations, `ASM_` assumptions, `MAP_` model-map rows, `CHG_` changes.
A prefix is followed by an alphanumeric token (`[A-Za-z0-9._-]`), e.g. `SRC_IEA_WEB_2023_NG_PWR`.
IDs are non-blank and unique within their table. `GAPS.csv` has no ID; its `item` is the key.
Reference lists accept semicolon, comma or whitespace separators and may mix ID types.

## SOURCES.csv — where a number came from

| Column | Notes |
|---|---|
| `source_id` | `SRC_…` |
| `provider`, `product`, `edition` | publisher, dataset, version |
| `reference_period`, `geography`, `variable` | what the number describes |
| `source_unit` | unit **as published**, before any conversion |
| `exact_locator` | **required** — the sheet, table, page or query that returns the number |
| `url` | public URL, or a ledger-relative path when the only copy is retained locally |
| `access_date` | **required**, ISO `YYYY-MM-DD` |
| `license` | redistribution terms |
| `sha256` | digest of the retained file, verified by opening it |

Optional: `local_file` (retained copy when `url` must stay a URL), `notes`.
A source needs a `url` or a `local_file`. A `sha256` is only accepted when a local file is named
and its bytes hash to that value; a digest with nothing to compare against is a failure, and a
retained file with no digest is also a failure.

## CALCULATIONS.csv — how a number was transformed

| Column | Notes |
|---|---|
| `calculation_id` | `CALC_…` |
| `formula` | the arithmetic, readable without the script |
| `source_ids`, `assumption_ids`, `input_calculation_ids` | inputs; at least one is required |
| `input_values`, `input_units` | the actual numbers that went in |
| `output_value`, `output_unit` | the number that came out |
| `script_path`, `script_version` | when code produced it; a path requires a version |

`input_calculation_ids` forms a DAG. Cycles are a failure.

## ASSUMPTIONS.csv — a number with no source

| Column | Notes |
|---|---|
| `assumption_id` | `ASM_…` |
| `statement` | what is assumed, in one sentence |
| `central_value`, `unit` | **required** — the actual number, not a description of it |
| `evidence_source_ids` | supporting sources, if any |
| `lower_bound`, `upper_bound` | only where sensitivity-tested; must bracket the central value |

## MODEL_MAP.csv — the model value itself

| Column | Notes |
|---|---|
| `map_id` | `MAP_…` |
| `model_file` | one file, never a glob; `*` and `?` are rejected |
| `parameter`, `entity`, `mode`, `scenario`, `years` | the coordinates of the value |
| `value_or_expression`, `model_unit` | the value as the model sees it |
| `evidence_ids` | **required** — any mix of `SRC_`/`CALC_`/`ASM_` IDs |
| `superseded_by` | blank while active; a `CHG_` ID once the row is retired |

Evidence type is **derived, never stored**: a calculation anywhere in the lineage makes the value
`derived`, otherwise an assumption makes it `estimated`, otherwise it is `direct`. An optional
`evidence_type` column is checked against the derived value rather than trusted. Retired rows keep
their lineage — never delete a row — but they no longer provide input coverage.

## GAPS.csv — what is deliberately absent

| Column | Notes |
|---|---|
| `item` | the parameter or flow not represented |
| `why_absent` | **required** — the reason, not a restatement |
| `upgrade_source` | what would close the gap |

## CHANGES.csv — every change, with its triage class

| Column | Notes |
|---|---|
| `change_id` | `CHG_…` |
| `date` | ISO `YYYY-MM-DD` |
| `class` | Administrative chronology: `A` structural cleanup, `B` evidence-based parameter/model refinement, `C` outcome-referenced calibration record |
| `description`, `model_objects` | what changed and to what |
| `evidence_path` | the artifact proving the change was sound; **required for class A** |
| `map_rows_affected` | `MAP_` IDs |
| `resolve_status` | `objective_unchanged`, `resolve_required` or `resolved` |
| `author`, `commit` | who, and the revision (7-40 hex) |

A class A change asserts no model value moved, so it may not touch a live mapping: every
`MAP_` row it names must already carry `superseded_by`. That is what makes the fast path
auditable rather than merely fast.

The class is metadata, not a workflow router or an evidence waiver. It must not downgrade a
coupled evidence-based country refinement to a token check, and it never authorizes fitting a
parameter to an observed outcome contrary to the non-forcing rule.

## What this validator deliberately does not do

It never records a digest of a file it wrote itself, never re-hashes content already inside
another hashed artifact, and never accepts a digest it has not compared against bytes on disk.
A checksum that is only pattern-matched proves nothing, so it is a failure here, not a pass.
