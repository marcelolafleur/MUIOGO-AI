# MUIOGO API — observed endpoint reference

Status: living document. Everything in "Verified" was exercised headless against
MUIOGO @ `3db8b816` (2026-07-27) with a plain HTTP client and no GUI; payload
shapes are copied from working calls. Endpoints under "Present, not yet
exercised" were read in the route code but not driven.

Base URL: `http://127.0.0.1:5002` (port from `PORT` env; server started with
`<root>/.venv/bin/python API/app.py` — no browser opens; MUIOGO's start.sh is
what opens the browser).

## Session model

- Flask cookie session; one key: `osycase` = the selected case name.
- `GET /getSession` → `{"session": <case-or-null>}` — works cold, also a good
  readiness probe.
- `POST /setSession` `{"case": "CLEWs Demo"}` → `{"osycase": "CLEWs Demo"}`.
  404 if the case directory doesn't exist; `{"case": null}` clears.
- Most read/run endpoints take `casename` explicitly and work from a cold
  session. **Session-gated** (403/400 unless `osycase` matches): `copyCase`,
  `deleteCase`, `downloadCSVFile`, `downloadResultsFile` (and other download
  routes by the same pattern).

## Verified endpoints

| Endpoint | Method | Payload / params | Returns |
|---|---|---|---|
| `/getSession` | GET | — | `{"session": name-or-null}` |
| `/setSession` | POST | `{"case": name}` | `{"osycase": name}` |
| `/getCases` | GET | — | `["CLEWs Demo", ...]` |
| `/copyCase` | POST | `{"casename": name}` (session must match) | message; creates `<name>_copy` |
| `/deleteCase` | POST | `{"casename": name}` (session must match) | message |
| `/generateDataFile` | POST | `{"casename", "caserunname"}` | writes `res/<run>/data.txt` |
| `/run` | POST | `{"casename", "caserunname", "solver": "cbc"\|"glpk"}` | see below |
| `/getResultCSV` | POST | `{"casename", "caserunname"}` | list of result CSV names |
| `/downloadCSVFile` | GET | `?caserunname=<run>&file=<name>.csv` (session-gated) | CSV bytes |
| `/downloadResultsFile` | GET | `?caserunname=<run>` (session-gated) | raw `results.txt` |

### `/run` semantics (important)

- **Synchronous**: the request blocks until the solver finishes (demo case:
  ~1–4 s with CBC). Client timeouts must allow for real model sizes.
- **HTTP status is not the run status**: solver failures still return 200.
  The JSON body's `status_code` (`"success"`/`"error"`) is the real signal;
  `timer` carries the solver's result line, `glpk_message`/`cbc_message` the
  solver stdout.
- **Solver choice**: `"cbc"` is the GUI default and works — it preprocesses
  `data.txt` → `data_processed.txt`, builds `lp.lp` with glpsol `--check`,
  solves with CBC. `"glpk"` is broken at `3db8b816`: that branch skips
  preprocessing and feeds raw `data.txt` to the preprocessed model
  (`model.v.5.4.txt`), which fails on `MODEperTECHNOLOGY` (upstream fix filed
  from this work).
- Re-running deletes the run's previous results first.

### Solver prerequisites

`glpsol` and `cbc` binaries must be resolvable (env var, PATH, or platform
standard locations — see MUIOGO `docs/ARCHITECTURE.md`). On macOS:
`brew install glpk cbc`. Resolution happens per request; no server restart
needed after installing.

## The /ogc layer: MUIOGO's own model registry (verified 2026-07-28)

MUIOGO already tracks which OG country models are installed, so tooling should
read and write that registry rather than keeping its own list.

| Endpoint | Method | Notes |
|---|---|---|
| `/ogc/getCalibrationCatalog` | GET | what can be installed; rows under **`countries`**, read live from the upstream register |
| `/ogc/getInstalledCalibrations` | GET | what IS installed; rows under **`calibrations`** — a different key from the catalogue, so handle both |
| `/ogc/registerLocalCalibration` | POST | adopt a model already on disk: `{country_id, country_name, local_path, package_name, run_uv_sync}` |
| `/ogc/installCalibration` | POST | install a new one via the upstream OG-Core installer |
| `/ogc/getInstallStatus` | GET | `?install_id=` — both of the above are **asynchronous jobs** |

Two things that will bite:

- **The two list endpoints use different keys** (`countries` vs `calibrations`).
  A client that only reads one silently reports nothing installed.
- **Registration is asynchronous.** `registerLocalCalibration` returns an
  `install_id` immediately; the registry file
  (`<og-state>/og_calibrations_installed.json`) appears only once the job
  finishes. Poll `getInstallStatus`, or re-read the registry, rather than
  checking straight after the call.

The registry's location comes from `MUIOGO_OG_DATA_DIR` (default
`~/.muiogo/og-state`), and models from `MUIOGO_OG_MODELS_DIR` (default
`~/.muiogo/og-models`). A server started without those pointed at the right
place will not see models registered elsewhere.

## The /clews layer: CLEWs country installs (MUIOGO PR #519+, not yet at the pin)

The CLEWs twin of `/ogc`: where `/ogc` installs code (an OG model repo with its
own venv), `/clews` installs data — case archives declared in a country repo's
`clews-country.json` manifest, downloaded and sha256-verified by the server,
then imported through the same pipeline the GUI's restore uses. Added by
EAPD-DRB/MUIOGO PR #519; a server at the current pin answers 404 on all of
these (the client and install.sh degrade to the legacy path).

| Endpoint | Method | Notes |
|---|---|---|
| `/getVersion` | GET | `{muio_version, accepted_case_versions}` — check before sending archives |
| `/clews/getCountryCatalog` | GET | rows under **`countries`**; empty + `catalog_source: "none"` unless a register URL is configured (`MUIOGO_CLEWS_CATALOG_URL`) |
| `/clews/getInstalledCountries` | GET | rows under **`cases`** — every case with provenance, reconciled against DataStorage on each read; hand-added cases show `managed: false` |
| `/clews/inspectSource` | POST | `{source_type: repo_url\|local_path, ...}` → the manifest's menu (vintages, cases, collisions, version gate), nothing downloaded |
| `/clews/installCountry` | POST | same body + optional `vintage`, `cases[]`; **asynchronous job**, checksum mismatch installs nothing, existing cases report `already_exists` |
| `/clews/getInstallStatus` | GET | `?install_id=` — per-case `results` on completion |
| `/clews/checkCountryUpdate` | POST | `{casename}` — compares recorded vs published checksum; check-only |
| `/clews/cancelInstall` | POST | `{install_id}` |

There is deliberately no unregister and no overwrite: the installed list follows
the disk (remove a case with `/deleteCase`), and replacing a case is a
deliberate delete + reinstall.

## Present, not yet exercised

From `API/Routes/` at the same commit — payloads unverified:

- Case data: `/getDesc`, `/getParamFile`, `/saveParamFile`, `/updateData`,
  `/saveCase`, `/saveScOrder`, `/getResultData`, `/resultsExists`,
  `/prepareCSV`, `/downloadCSV`, `/importTemplate`
- Runs: `/createCaseRun`, `/updateCaseRun`, `/deleteCaseRun`,
  `/deleteScenarioCaseRuns`, `/batchRun` (CBC hardcoded), `/cleanUp`,
  `/validateInputs`, `/readDataFile`, `/readModelFile`, `/readLogFile`,
  `/saveView`, `/updateViews`, `/downloadDataFile`, `/downloadFile`
- OG-Core (`/ogc/*`): `/getCalibrationCatalog`, `/getInstalledCalibrations`,
  `/checkCalibration`, `/installCalibration`, `/registerLocalCalibration`
- Upload & S3 sync routes.

Next to exercise (Phase-1 scenarios work): `/createCaseRun`, `/updateData`,
`/batchRun`, `/readLogFile`.
