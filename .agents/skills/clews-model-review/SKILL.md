---
name: clews-model-review
description: Audit a MUIOGO CLEWs model under WebAPP/DataStorage/ for structural and data consistency against the NamibiaCLEWs benchmark. Also gates whether an object is safe to delete (--removable). For calibration quality use assess-clews-calibration.
---

# CLEWs Model Review

Evaluate whether a MUIO/OSeMOSYS **CLEWs** model (a folder under `WebAPP/DataStorage/`) is well-structured, and flag data inconsistencies. **NamibiaCLEWs** is the reference benchmark: a standard, solid CLEWs model — nothing fancy methodologically, just done right.

## Scope — which model(s) to review

The invocation arguments name the model(s) to review, matched to folder names under `WebAPP/DataStorage/`:
- **One model:** the argument is a model name, e.g. `NamibiaCLEWs` or `Philippines` → review only that model.
- **Several models:** space-separated names → review each.
- **No argument:** review every model folder found under `WebAPP/DataStorage/`.

Match the argument to the actual folder name (resolve fuzzy input like "Namibia" → `NamibiaCLEWs`; folder names with spaces such as `CLEWs Demo` must be quoted when passed to the script). If the name doesn't match any folder, list the available folders and stop rather than guessing.

## How to run

1. Run the bundled checker (auto-discovers models, or name specific ones):
   ```bash
   python .claude/skills/clews-model-review/audit.py                    # all models
   python .claude/skills/clews-model-review/audit.py NamibiaCLEWs       # one or more
   python .claude/skills/clews-model-review/audit.py --datastorage <path> <model>
   ```
   It prints per-model findings tagged `FAIL` / `WARN` / `INFO`, plus a summary. Exit code is non-zero if any `FAIL` is present (usable in CI).
2. Interpret the output against the rubric below and write the verdict as a short scorecard (see Output).
3. For anything the script flags, spot-check the underlying data before reporting it as real (e.g. confirm a "wrong unit" isn't compensated by the activity ratio — see the DESWAT note below).

## Data format (how models are stored)

Model folders are **git-ignored local data** (`.gitignore`: `WebAPP/DataStorage/*`, only the shared config JSONs tracked). Each folder has:
- `genData.json` — sets/metadata: `osy-tech`, `osy-comm`, `osy-emis`, `osy-scenarios`, `osy-techGroups`, `osy-years`, `osy-ts`/`osy-se`/`osy-dt`/`osy-dtb`, `osy-constraints`, `osy-mo`.
- Data files named after their OSeMOSYS **index set**: R=Region, Y=Year, T=Technology, C=Commodity, E=Emission, S=Storage, Ts=TimeSlice, M=Mode. Shape: `{ParamId: {ScenarioId: [ {TechId/CommId..., "2019": v, ...} ]}}`. Base scenario `SC_0`; others store `null` = inherit base.
- `res/<label>/results.txt` — solve output; first line is solver status ("Optimal ..."). No `res/` ⇒ never solved.
- Tech/comm/emis referenced by opaque IDs (`TEC_*`, `COM_*`, `EMI_*`, `SC_*`); resolve via genData. Param→file→default map is `WebAPP/DataStorage/Parameters.json`.

## Rubric — markers of a well-structured model (Namibia does all 7)

1. **Full CLEW integration with cross-sector links** — Energy (power fleet + fuel/electricity imports + sectoral demands), Land/Agriculture (land-use classes, crops × irrigated/rainfed × input level, livestock, crop trade), Water (surface/ground/desal supply vs sectoral demand + precipitation), Climate (emissions + limits). The *links* matter: irrigation water & diesel→crops; cooling water→power; land clearing→biomass→power; precipitation→water balance.
2. **Systematic naming + tech groups** — consistent prefixes (DEM/IMP/EXP/LND/LVS/MIN/PWR/BST=backstop/DUM=dummy), real descriptions, meaningful tech groups.
3. **100% referential integrity, zero orphans** — every ID used in data exists in genData; nothing defined is unused.
4. **Complete parametrization** — capital/fixed/residual cost for every tech, operational life, demands (SAD/AAD).
5. **Sound technique** — backstop techs (BST*) for feasibility, dummy techs (DUM*) + constraints (e.g. land balance) for accounting, emission penalty/limit machinery.
6. **Policy scenarios that solve** — multiple active scenarios all reaching Optimal, backstops ~zero in base (well-calibrated), meaningful scenario logic.
7. **Sensible horizon/resolution & unit discipline** — one unit per physical domain; deliberate exceptions are compensated in the activity ratios.

## Checks (each = a real defect class; severity)

- **Referential integrity** [FAIL] — any complete
  TechId/CommId/EmisId in data missing from genData. Parse IDs from JSON keys
  and scalar values; do not regex serialized text. Derived-model IDs may
  contain underscores, periods, colons or hyphens.
- **Scenario-ID consistency** [FAIL] — any `SC_*` in a data file not in `osy-scenarios` (stale/orphaned). *Namibia example: `RY.json` alone referenced dead SC_13ijj/SC_tqww6/SC_wjl7a.*
- **Placeholder descriptions** [FAIL if all, else WARN] — Desc "" or "Default commodity". *LaoPDR: all 403 techs + 88 comms — hallmark of an un-curated "otoole converted" import.*
- **Dangling technologies** [WARN/FAIL] — no IAR and no OAR in any scenario. *e.g. LaoPDR's 6 PWRBIN/PWRBOU nodes; or an export tech that was never given its input link.*
- **Stranded outputs / RES "Missing Target"** [WARN] — a commodity **produced (OAR) but with no sink at all**: not consumed by any technology's activity (IAR) *or* capacity (INCR/ITCR), and no demand (SAD/AAD). These are genuine model dead-ends and render as **"Missing Target Technology"** in MUIO's Dynamic Diagram. *Namibia example (since fixed): `CRPONIE`/`CRPMTPE` "for export" commodities produced by EXPONI/EXPMTP but consumed by nothing.* Verify each before reporting — some (land-use-change accounting like `AGRLUC`/`DUM`) may be intentional terminals; others (e.g. a sector "demand" commodity given no demand) are real gaps. **Nuance:** MUIO's RES draws only IAR/OAR links (not INCR/ITCR), so a commodity consumed *only* via capacity (e.g. `LNDSOL` → solar-plant capacity) also shows as "Missing Target" in the diagram but is **not** stranded — the check deliberately does not flag those. See the export convention below.
- **YearSplit sums to 1.0** [WARN] — sum of YS across timeslices per year must = 1. *Namibia & Zambia both = 1.001 (shared template, 3-decimal rounding).*
- **Unit consistency in a single-fuel domain** [WARN] — e.g. diesel split PJ vs TJ. *Namibia INDDSL labelled TJ but numerically PJ; Zambia water strings "10⁹m³" vs "10⁹m³/yr".* NOTE: a different scale can be legitimate — Namibia DESWAT in 10⁹m³ is correct because the electrolysis IAR (0.009) compensates. Verify before flagging.
- **Sector coverage** [WARN] — detect Energy/Land/Water by CODE prefix (works even with missing descriptions); Climate by emissions count.
- **Organization** [INFO] — ≤1 scenario = no policy analysis; ≤1 tech group on a large model = hard to navigate.
- **Solve status** [WARN] — `res/` present and every `results.txt` is
  "Optimal". Result-folder names are run labels, not scenario labels; compare
  them with `view/resData.json` when determining whether a run is registered,
  incomplete or possibly stale.

## Modeling conventions

- **Exports are terminal (consume-only).** Model an export technology so it *consumes* the exported commodity (IAR) and produces nothing — its own activity level then equals the exported volume (readable in `UseByTechnology`/`RateOfActivity` results). This renders as a clean "final technology" in the RES diagram. Do **not** give an export technology an OAR to a dedicated "for export" commodity: that commodity has no downstream consumer or demand, so MUIO draws it into a "Missing Target Technology" node. Keep all export technologies consistent on this. *(In the RES diagram, a commodity is only a valid sink if it is consumed by a technology or has a demand — "Final demand".)*
- Export revenue is carried by a negative `VariableCost` on the export technology; check these are consistent and realistic across exports (Namibia's ranged from −1346 to +0.0001, i.e. some had no real export price).

## Output

Report a short scorecard: one line per model with a verdict (BENCHMARK / STRONG / GOOD / GOOD-BUT-UNPROVEN / WEAKEST-NEEDS-CURATION or similar) and its open issues by severity. Lead with the verdict, then FAILs, then WARNs, then INFOs. Keep it to what changes the reader's decision.

## Updating this skill

Add or adjust checks by editing this file and `audit.py`. When you learn a new defect pattern or change the benchmark, update both the rubric here and the corresponding check in the script so they stay in sync.

## Related skills

- `calibrate-clews-model` — replacing generic country inputs and repairing physical
  connections with complete provenance.
- `assess-clews-calibration` — whether the model is calibrated well enough for a question.
- `muiogo-provision` — MUIOGO's ten input-consistency checks, before a long solve.
- `muiogo-run` — solving a case; `muiogo-analyze` — comparing and charting the results.

These live in the MUIOGO-AI collection; if one is not available to you,
do the job directly and say which skill would have covered it.
