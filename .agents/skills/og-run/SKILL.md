---
name: og-run
description: Installs an OG-Core model (OG-Core or a country repo) with OG-Core's official installer and runs its shipped example script unchanged - baseline and reform from that install's own environment, in parallel, with the Anderson solver - builds a multi-industry calibration, monitors the run and collects the output. Use when asked to run, solve or re-run an OG model (OG-Core, OG-USA/PHL/ZAF/IDN/BRA/ETH), to produce a baseline or reform, to benchmark or test a code change, to check whether the model fails or misbehaves, or when another skill needs OG output that does not exist yet.
---

# Run an OG-Core country model

An OG solve is a different animal from a CLEWs solve: minutes rather than seconds, parallel
worker processes, and a two-stage structure (steady state, then transition path). Treat
launching one as a decision the user makes.

The model owner's run rules are in `../OG_RUN_RULES.md` and win over anything older,
including the AGENTS.md estimate of "~35 min – 2 hr" for a full example run. In short: a healthy
baseline takes **under ten minutes** (steady state in seconds to a minute or two, transition path
about 5–7 minutes); **install with OG-Core's official installer** (`scripts/install.sh`) and run
**the shipped example script unchanged** from that install's environment, with nothing added;
**always parallel**; the **Anderson** solver with `nu` 0.2 or lower, checking both values, since
some repos set Anderson but leave `nu` at 0.4; validation runs offline; launch only on the user's
explicit go.

## Which world

This skill acts on **one** world: the runtime installation reached by `muiogo-ai`,
unless the user explicitly asked for their own live one (`muiogo-live`). Never use
bare `muiogo`, and never fall back to it. Every command prints a `world:` line to
stderr — read it, and name that world when you report a run or a number. Worlds
hold different OG model registries, so a model installed in one is invisible in
the other. Full rules: `../WORLD_DISCIPLINE.md`.

Orient first with `muiogo-ai status` (see `muiogo-workspace`) to find the installed
country models. Each lives in its own checkout with its own `.venv`.

## Install first, with the official installer

Every run whose result you will report starts from a copy installed by OG-Core's installer, as
`scripts/QUICK_INSTALL.md` in PSLmodels/OG-Core describes. Do not build the environment by hand
(conda, `uv sync` in a worktree you made, `PYTHONPATH`, `pip install -e` of another checkout).

```bash
curl -fsSL https://raw.githubusercontent.com/PSLmodels/OG-Core/master/scripts/install.sh -o install.sh
mkdir -p <new parent folder>
bash install.sh --repo <key> --dest <new parent folder> --yes     # --list shows the keys
# a branch or fork under test, into its own folder:
bash install.sh --repo-url <git URL> --branch <branch> --dest <another new folder> --yes
```

The installer clones the repo, runs `uv sync --extra dev`, and checks the import. It refuses a
parent folder that does not exist, so create it first. Use a new folder: never install over a
checkout that holds someone's work.

## The rule that matters most

**Run the shipped example, unchanged, from the installed copy's own environment and directory.**
No driver script of your own, no edited copy, no changed settings, no monkeypatching, and nothing
injected to observe the run (wrappers, counters, `sitecustomize`, dask worker plugins). To learn
something about a run, read its saved output afterwards. A result from anything else is a lead,
not a finding: say so, and never report a model failure from it.

**Run the model from its own environment, from its own directory.** Never import
an OG package into another environment, and never run a country model with
another checkout's interpreter — the packages shadow each other and you will
solve the wrong model without any error.

Before launching anything, run the preflight in `og-run-preflight`. It exists
because a battery once ran silently against stale code. A passing preflight is a
precondition, never an authorization.

If the preflight cannot run, the minimum by hand is: print the branch and HEAD of the
checkout, and confirm the model's own interpreter imports the package from inside that checkout.
If it points elsewhere, stop; that is the finding.

## Launching a run

Country models ship example scripts that define the baseline and the reform:

```bash
cd <og-models>/OG-PHL
ls examples/
#   run_og_phl.py                   single-industry baseline + reform
#   run_og_phl_multi_industry*.py   multi-industry: a demo or a calibration, by branch
```

They take no arguments; the reform is expressed inside the script as parameter
updates. Run one from the installed folder with its own environment, exactly as the
installer's instructions say:

```bash
cd <installed folder>/OG-PHL
source .venv/bin/activate
python examples/run_og_phl.py          # or, equivalently: uv run python examples/run_og_phl.py
```

What it does: starts a pool of worker processes (`min(cpu_count, 7)`, one thread each),
solves the **baseline** into `examples/OG-PHL-Example/OUTPUT_BASELINE/`, applies the
reform's parameter changes, solves the **reform** into `.../OUTPUT_REFORM/`, and closes the
pool. The paths are built from the script's own location, so they do not depend on the
working directory. Each stage writes `SS/SS_vars.pkl`, `TPI/TPI_vars.pkl` and
`model_params.pkl` under its output directory.

Set the solver the way the owner's rules require: `TPI_outer_method="anderson"` and a `nu` of
0.2 or lower belong in the repo's packaged parameters, not in a one-off script
(`og-country-calibration` covers this). If the repo does not set them yet, run the example as
shipped and say so, and ask whether to propose the parameter change. Do not make a copy of the
example with different settings unless the user asks for one.

Propose the run with its expected duration (under ten minutes for a healthy baseline, the
reform about the same) and wait for the user's explicit go. There is no cheap smoke version: the
repo's `test_run_example.py` only checks the process is still alive after five minutes and
produces no usable output.

Things that bite in a headless session:

- **The UN population token.** Recent ogcore (0.20 and later) looks for it in the
  `UN_API_TOKEN` environment variable, then a per-user file, then a deprecated
  `un_api_token.txt` in the working directory. It never prompts when no one is at the
  keyboard: it falls back to the EAPD-DRB Population-Data archive instead. Older ogcore
  reads only the working-directory file and can prompt. If a run seems to hang early with
  no output, check this first.
- **A run makes live API calls.** Whenever the machine is online, the example calls
  `Calibration(p, update_from_api=True)`, which refreshes parameters from live sources and
  can overwrite curated values (`og-country-calibration` covers the risk). Say so when
  proposing the run, and note whether it ran online.
- **`uv run` re-syncs the environment to the lockfile.** If the run needs an ogcore that is
  not the locked release (a local build or a branch), `uv run` silently swaps it out. In a
  repo with no `uv.lock`, `uv run` resolves and installs fresh, with the same effect. Use
  `.venv/bin/python` in both cases, or create the environment deliberately first.
  Invoke `.venv/bin/python examples/...` directly in that case, and check
  `import ogcore; print(ogcore.__version__, ogcore.__file__)` first.
- **Custom drivers and relative paths.** If you ever drive the model from your own script,
  note that `Specifications` defaults `baseline_dir` to the relative string
  `OUTPUT_BASELINE`. The shipped examples set absolute paths and are not affected.

For a background run, launch it (after the user's go) under `nohup` or a terminal
multiplexer, with unbuffered output teed to a log so progress survives a disconnect:

```bash
nohup uv run python -u examples/run_og_phl.py > og-phl-run.log 2>&1 &
```

Then monitor rather than re-launching, and report status to the user at intervals without
being asked:

- **Running or finished?** The transition path logs `Time path iteration complete.` when it
  ends. Otherwise compare the log's last-modified time and the process's CPU time between
  two checks. When matching the process with `pgrep -f`, use a pattern that cannot match
  your own check command, or you will read your own `pgrep` as the run.
- **Healthy?** Add up the CPU of all the worker processes, not just the main Python
  process. During the transition path they should keep the machine close to fully busy; a
  third of the machine there means too few workers or a serial run. On older ogcore the main
  process is the bottleneck during the steady state and idle workers are expected (each
  evaluation re-sent the parameters to the workers); a slow steady state there points to the
  ogcore version or a cold start, not the worker count.
- **On time?** Past about ten minutes for a baseline, check the setup before waiting longer.

To change what is solved (only when the user asked for a different scenario or setting),
do not edit the shipped example in place. Copy it and change only what the run needs: the reform's parameter dictionary, the solver settings above, and
the output folder. Keep the example's structure (the worker pool, the calibration call, the
runner), because the owner's rule is to run the way the examples do. Say which parameters
you changed. `og-country-calibration` covers which parameters are defensible to
change and the traps in each block.

## Building a multi-industry calibration

A freshly installed country model is single-industry. Coupled OG-CLEWS work needs
multi-industry, because a single-industry model has no electricity industry for an
energy price to act on — the link reports this as `couplable=0`.

Which multi-industry script you have depends on the repo and branch. The calibrated
work lives on each repo's multi-industry branch; the default branch may carry only a
demo or an upstream placeholder under a similar name (OG-PHL's main has a hand-coded
two-industry demo). Check what the script loads before running it, and use
`og-multi-industry-calibration` to judge whether a calibration is real and to build one.

Running the calibrated example follows the same rules, with two differences: it may
first solve its steady state by continuation (a couple of minutes), and the baseline
plus reform take tens of minutes rather than ten. Propose before launching, monitor by
log. Afterwards register it with the link and confirm the calibration is recognised
(see `og-clews-linked-run`).

## Collecting the results

A completed run leaves two directories, and they are what every downstream skill
consumes:

```
OUTPUT_BASELINE/    the baseline steady state and transition path
OUTPUT_REFORM/      the same under the reform
```

Keep them together and record what produced them: the country repo, its branch
and commit, the ogcore version, which example script, which parameters were changed
(solver settings included), whether it ran online, and the run date. Without that, a comparison months later cannot be defended — the same
discipline the CLEWs side gets automatically from its `RUN.json`.

Never edit files inside an OUTPUT directory. To redo a run, re-solve.

## Checklist

Copy this and work through it:

```
- [ ] Installed with OG-Core's official installer (scripts/install.sh) into a new folder;
      a branch under test gets its own install (--repo-url ... --branch ...).
- [ ] The run is the shipped example script, unchanged, nothing injected. Any deviation was
      asked for by the user and will be named in the report.
- [ ] og-run-preflight reports GO for the repo and branch the task names.
      If NO-GO: fix what it names and run it again. Do not launch.
- [ ] Solver set: TPI_outer_method="anderson", nu 0.2 or lower (repo default or the copy).
- [ ] Proposed to the user: exact command, expected duration, online or not. Launch only
      after the user's explicit go (or the user launches it).
- [ ] Monitor the log. If it dies at once: back to the preflight (environment, not economics).
      If it runs far past ten minutes or the distance stops falling: og-solver-diagnosis.
- [ ] Provenance written next to the output folders (see above).
```

## When a solve misbehaves

Do not restart it and hope. A solve that fails to converge, oscillates, or
returns implausible aggregates has a diagnosable cause — hand off to
`og-solver-diagnosis`, which carries the protocol and a real failure taxonomy.
Re-running a long solve on a guess wastes hours.

If the run dies immediately, it is almost always environment rather than
economics: wrong interpreter, wrong branch, missing data. Re-run the preflight.

## Handing off

- Before launching: `og-run-preflight`.
- Which parameters to set, and why: `og-country-calibration`.
- Designing the reform, the standard deliverable, and bespoke analysis of finished OUTPUT
  dirs: `og-scenario-report`.
- A solve that will not converge: `og-solver-diagnosis`.
- Tracing a calibrated number to its source: `calibration-provenance`.
- Coupling to the energy system: `og-clews-linked-run`.
- Explaining what the model and its calibration mean: `muiogo-explain`.

## Approval gates

Propose, draft, and prepare; the user decides. Inspecting a model, running the
preflight, and reading finished output are free. **Stop and ask before launching
any solve** — state the command and the expected duration, and launch only after the user's
explicit go. (A steady-state-only check that takes seconds, inside a calibration task the user
has already started, follows `og-country-calibration`; a full baseline or reform needs the go.) One go can cover an itemised batch (say, the same example in five listed
countries); it never extends to runs that were not on the list. Stop before pushing,
PR-ing, merging, or deleting anything.
