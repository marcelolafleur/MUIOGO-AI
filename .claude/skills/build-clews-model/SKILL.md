---
name: build-clews-model
description: Build or evolve an uncalibrated OSeMOSYS/CLEWs country model from CLEWs Global and package it as a solved, source-traceable MUIO case. Use for new country builds, new versions of existing country models, GeoCLEWs adaptation, otoole/MUIO import, or delivery packaging. Not for calibration, and not for structural cleanup - see clews-model-fix.
---

# Build a CLEWs country model through MUIO

Produce three separately reported things:

1. a reproducible, solved raw CLEWs Global country model;
2. a complete MUIO representation of it, with every difference explained;
3. a machine-validated provenance package.

Preserve GeoCLEWs spatial processing, OSeMOSYS Global energy inputs, `clewsy` nexus
integration, the upstream formulation, and an open solver. Treat MUIO import as a separate
representation phase — never describe an import fix or a formulation workaround as country
calibration.

## Boundary

**Do not use historical observations to make model results match history.** The test, applied
to any parameter or constraint: *would this exact change still be made if no historical
outcome were known?* If no, do not apply it; retain the observation as a diagnostic benchmark
or gap for later assessment. Binding for this whole workflow,
including the MUIO phase. Before delivery, `python scripts/audit_no_forcing.py` must report
zero failures.

Full rules — the forbidden-pattern list, and how OSeMOSYS activates bounds (`-1` disables an
upper limit but `0` is a live lock, which forcing checks get wrong):
[references/non-forcing.md](references/non-forcing.md).

`audit_no_forcing.py` is the only script here that needs a third-party package — PyYAML, to
read `config.yaml`. Every other script in this skill is stdlib-only, so switching interpreters
to clear this one import will not change any other script's result. Check before you start:

```bash
python3 -c "import yaml" || pip install --target .deps pyyaml   # then PYTHONPATH=.deps
```

Install beside the work rather than into the interpreter: bundled and minimal Pythons
routinely lack PyYAML, a stock system Python and MUIOGO's `.venv` both lack it, and a scratch
target directory needs no write access to any shared environment. Do not hand-roll a YAML
parse to avoid the dependency — a key this skill checks for that a partial parser misses
reads as absent, which turns a forcing failure into a silent pass.

Without PyYAML the script still runs its input-file checks and reports `config-unreadable` as
a **failure**, so a config that was never audited cannot clear this gate. Treat that finding
as work outstanding, not as environmental noise to be argued past.

## Provenance

Populate the ledgers as you go — coverage mapping is not a delivery-time activity. Every
source needs an `exact_locator` (page, table, sheet, cell, dataset variable or query); a bare
URL is insufficient and blocks delivery. Every assumption needs a `central_value` and a
`unit`. Register unavailable lineage as a documented gap; never leave an active value silently
undocumented.

For a new version of an existing model, begin with a complete copy of the current canonical
ledger and its retained evidence. Carry unchanged records forward, add records for new inputs,
and update or supersede records for changed inputs. A previous-version reference may record
chronology, but it must never replace the inherited source, calculation, assumption or model-map
records. The new version's ledger must stand on its own without opening an earlier package.

Three validation checkpoints, and only three:

```bash
python scripts/validate_provenance.py PKG --stage scaffold
python scripts/validate_provenance.py PKG --stage build
python scripts/validate_provenance.py PKG --stage delivery
```

[references/SCHEMA.md](references/SCHEMA.md) is the canonical six-ledger schema and the one
invariant. The checkpoint wrapper applies that schema to `data_sources/`, checks active model
inputs and `config/config.yaml` against `MODEL_MAP.csv`, then applies the separate country-
package and frozen-baseline checks. `DATA_SOURCES.md` is explanatory narrative, not a seventh
ledger.

## Workflow

1. **Scaffold and define.** For a new model, run
   `python scripts/init_country_package.py PKG --country C --iso3 ISO`, then the `scaffold`
   checkpoint. For a successor version, copy the complete current canonical ledger and retained
   evidence into the new package first, then continue that ledger rather than starting a blank
   or delta-only one. Record country, ISO3, horizon, administrative resolution, climate pathway,
   intended use, and both source locations. Label the scenario `raw`. Proceed on documented
   upstream defaults when the user gives only a country; ask only when a missing choice would
   change the model architecture.

2. **Pin both codebases.** Clone CLEWs Global recursively; record root and every submodule
   commit in `config/upstream_versions.json`. Record the MUIO version/commit. Run a
   dependency preflight and record exact versions. Never start from a calibrated country
   model. Code pins do not freeze data behind mutable URLs — record editions, access dates
   and checksums for downloaded inputs.

3. **Structural inputs.** Obtain boundaries and administrative layers. Populate `SOURCES.csv`
   with an exact locator for every dataset. Use observed geography, seasons and technology
   applicability as structural inputs only; keep historical performance data in a
   calibration-candidate inventory and apply none of it.
   → [references/country-adaptations.md](references/country-adaptations.md) before changing
   country structure, technology applicability, time definitions or crop mappings.

4. **Configure.** Native CLEWs Global configuration wherever possible. Complete
   `CURRENT_MODEL.md`, `MODEL_STRUCTURE.md`, `KNOWN_LIMITATIONS.md`, and add a dated
   `HISTORY.md` entry.
   → [references/provenance-and-layout.md](references/provenance-and-layout.md) for the
   package layout and the government-review table.

5. **Preflight before the expensive run.** Inspect the raster cache for stale, zero-byte or
   corrupt files and missing crop/variable/water combinations. Measure raster coverage over
   every boundary component. Detect multipart, island, coastal, antimeridian and
   invalid-geometry conditions before clustering. Run `python scripts/estimate_resources.py`.
   Stop on failed structural inputs — never discover a missing raster late.
   → [references/geospatial-preflight.md](references/geospatial-preflight.md).

6. **Technical corrections, only if needed.** Reproduce the defect on the pinned version
   first. Prefer a minimal general correction over a country-result override. Every
   correction keeps a fixture that fails before and passes after. For pinned revisions with
   the sample-country transmission block, run
   `python scripts/fix_clewsy_grid_mapping.py CHECKOUT/workflow/scripts/clewsy.py`.
   → [references/technical-corrections.md](references/technical-corrections.md).

7. **Run the native workflow.** GeoCLEWs → OSeMOSYS Global inputs → `clewsy` integration →
   convert, generate, solve, export. NaN-aware normalization; explicit constant-column
   handling; every retained land cell in production clustering. Select crops by exact
   source-item joins and write a machine-readable crop mapping. Stop on any non-zero
   subprocess status.

8. **Validate technical and nexus integrity.** Solver optimality, schema conformance, unique
   indices, complete sets, valid units, balanced timeslices. Confirm energy, land, crop,
   water and climate are physically linked, not merely colocated. Check land conservation,
   crop production/use, water accounting, energy balances, emissions. Report year-to-year
   discontinuities as raw-model behaviour. Compare with observations only to build a gap
   table marked **diagnostic — not fitted**. Then the `build` checkpoint.

9. **Import into MUIO.** Build a capability inventory for every populated parameter. Test
   worksheet aliases before the full import. Add `TECHGROUP` definitions (interface metadata
   — must not alter parameters). Use a country-local driver around MUIO's `ImportTemplate.py`
   and do not modify shared MUIO code. Refuse to overwrite an existing case silently.
   → [references/muio-import.md](references/muio-import.md) and
   [references/import-quality-gates.md](references/import-quality-gates.md).

10. **Repair and verify temporal structure.** Reconstruct each timeslice's season, day type
    and daily bracket from the authoritative `Conversionls/ld/lh.csv`, and `DaySplit` from
    the CLEWs CSV. Back up before repair. Assert one active member per timeslice per
    dimension. Solver success does not excuse a temporal mismatch.

11. **Import parity, before any workaround.** Round-trip through otoole and classify every
    source row as exact, implicit default, intentional transformation, unsupported or
    erroneous. Any lost or changed nondefault row is a hard failure without a tested
    representation. Report association expansion ratios and stop on unexplained dense
    Cartesian expansion. **Report `upstream_raw`, `muio_import` and `muio_final` separately —
    a later solve must never overwrite an earlier import failure.**

12. **Reserve-margin tags.** Test for native support first and use it when present.
    Otherwise apply the labelled UDC workaround — a workaround for unsupported tags, not
    calibration. Require `CURRENT` with zero mismatches before solving.
    → [references/reserve-margin-workaround.md](references/reserve-margin-workaround.md).

13. **Solve and validate MUIO.** Re-run the resource estimate on actual imported dimensions.
    Never reduce years, timeslices, clusters or technologies automatically — that is a
    modelling decision. Solve with a supported open solver; require optimal/feasible. Verify
    UDC rows appear in data and results. Record actual measurements beside the estimate.

14. **Package and validate.** Export a MUIO-compatible case ZIP (exclude regenerable LP/MPS
    unless asked; retain the generation command and solver log). Freeze the baseline with
    `python scripts/freeze_raw_baseline.py PKG --muio-archive muio/C_raw_MUIO.zip`, then the
    `delivery` checkpoint and `python scripts/validate_delivery.py PKG`.
    → [references/resource-and-packaging.md](references/resource-and-packaging.md).

## Permitted changes

Reproducible technical corrections; documented country adaptations; deterministic
compatibility changes; diagnostic comparisons that do not feed back; MUIO-only technology
groups and descriptions; one-off repair of importer-created time references from the
authoritative conversion matrices; nearest-valid-land-cell imputation under the documented
coverage thresholds; an explicit `GLOBAL, 0.05` discount-rate fallback only when CLEWs Global
supplies none; the labelled reserve-margin UDC workaround.

## Done when

The scripts enforce the mechanical gates — `audit_no_forcing.py`,
`validate_provenance.py` at all three stages, and `validate_delivery.py` must all exit 0.
Do not restate their checks here. What they cannot judge, and you must:

- the native workflow and the final MUIO run both solve, and their statuses are reported
  separately alongside `muio_import`;
- parity differences are *explained*, not merely counted;
- every crop proxy and consequential source choice is named in the government-review table
  with the agency that could validate it;
- each applied technical correction addresses software behaviour, not historical fit;
- unsupported inputs are explicitly inventoried rather than silently dropped;
- a successor version carries the complete prior ledger and retained evidence forward, and no
  previous-version reference substitutes for inherited provenance;
- any reserve-margin UDC is labelled a workaround, not an import;
- an Amber resource estimate has been explicitly accepted by the user.

## Delivery language

> This is a technically solved, uncalibrated CLEWs Global country model. It uses upstream
> defaults plus documented technical corrections and country adaptations, and it has been
> imported into MUIO with documented representation repairs. No parameters or constraints
> were introduced to force agreement with historical outcomes. Any reserve-margin UDC is a
> labelled workaround for unsupported native tags, not calibration. Historical calibration
> and policy constraints are separate later stages. Active inputs and modelling choices are
> linked through the package ledgers; documented provenance does not by itself prove that a
> source is accurate or fit for a particular boundary.

Report solver success as technical validity only.

## Related

- `clews-model-fix` — structural cleanup that cannot change a solved value.
- `clews-model-review`, `assess-clews-calibration` — checking what you built.
- `calibrate-clews-model` — replace generic inputs with sourced country data and repair
  physical connections after the basic solved build exists.
