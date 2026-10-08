---
name: og-run-preflight
description: "Checks, before any OG-Core or OG-CLEWS computation is launched (a steady-state or transition solve, a run_og_*.py example, a battery, an ogclews-link run), that every repo is on the intended branch and commit, that each interpreter imports the intended worktree's code, and that each worktree has its own venv. Use the moment a run is about to start, even if the environment looks right, and when a result looks contaminated or reproduces a known-buggy number."
---

# OG run preflight

A battery once silently ran a whole night on stale code from another worktree, contaminating
golden records. The cause was import shadowing — invisible at launch, expensive to
discover. This skill exists so that never recurs: **no solve, battery, or long computation gets
launched without a GO from the preflight script.** "It looks right" is not a check.

## Which world

This skill acts on **one** world: the runtime installation reached by `muiogo-ai`,
unless the user explicitly asked for their own live one (`muiogo-live`). Never use
bare `muiogo`, and never fall back to it. Every command prints a `world:` line to
stderr — read it, and name that world when you report a result or a number. Worlds
hold different OG checkouts and different model registries, so the same country
model can exist in both at different commits. Locate the checkout you mean with
`muiogo-ai status` rather than assuming a path. Full rules:
`../WORLD_DISCIPLINE.md`.

## The rule

Run `scripts/preflight.py` (bundled, stdlib-only) before every launch. It is deterministic and
read-only. If it prints `NO-GO`, do not launch — fix the failure, re-run the preflight, and only
launch on `GO`. Never work around a failure by hand-editing `sys.path` or exporting `PYTHONPATH`;
fix the environment the failure points at.

```bash
python3 scripts/preflight.py \
  --check <REPO>::<pkg>[,<dep-pkg>...][::<venv-python>] \
  [--check ...] \
  --run-cwd <dir the run launches from> \
  --entry-script <script the run executes>
```

- One `--check` per repo/environment involved in the run.
- First package name = the repo's own package (must resolve **inside** the repo).
  Comma-separated extras (e.g. `ogcore`) must resolve inside the repo or its venv — never a
  sibling checkout.
- `<venv-python>` defaults to `<REPO>/.venv/bin/python`.
- Always pass `--run-cwd` and (when the run executes a script) `--entry-script`: a plain `-c`
  probe alone does **not** reproduce script-dir shadowing, so probe with the run's own invocation
  style. Console scripts are immune to cwd shadowing; `python script.py` and `python -c` are not.

Single-repo example (a country model; `<country-repo>` is the absolute path of the checkout
under test, OG-PHL here):

```bash
python3 scripts/preflight.py \
  --check <country-repo>::ogphl,ogcore \
  --run-cwd <country-repo> \
  --entry-script <country-repo>/examples/run_og_phl.py \
  --params-json <country-repo>/ogphl/ogphl_default_parameters.json
```

`--params-json` loads the packaged parameters into `Specifications` the way the example does.
Pass it whenever the run loads a packaged JSON: a JSON that carries a parameter the resolved
ogcore does not know (an unreleased one, or one from a newer release) fails here in seconds
instead of at launch.

Cross-env example (ogclews-link, which subprocesses the OG model's own interpreter): one `--check`
per environment, with the OG side's interpreter taken from the model registry
(`og_model_registry.json` → `env_python`, `source_dir`) — not from memory:

```bash
python3 scripts/preflight.py \
  --check <ogclews-link checkout>::ogclews_link \
  --check <registry source_dir's repo root>::ogphl,ogcore::<registry env_python> \
  --run-cwd <ogclews-link checkout> \
  --entry-script <ogclews-link checkout>/experiments/run_battery.py
```

The link env must NOT import ogcore — so ogcore goes on the OG side's check line only.

## What the script verifies (and what a failure means)

| Check | Failure means | Fix |
|---|---|---|
| git branch + HEAD printed per repo | (informational — but confirm it's the branch you *intend*, not just any branch) | `git switch` in the right worktree |
| venv prefix inside the repo | shared/foreign venv; per-worktree-venv rule broken | `python -m venv .venv && .venv/bin/pip install -e .` in that worktree |
| import from neutral cwd lands in repo | **editable install points at another worktree** | `pip install -e <repo>` with that venv's pip |
| package not importable at all from a neutral cwd (INFO, not a failure) | it isn't installed and runs from its folder (e.g. MUIOGO's in-repo `oglink`), so nothing can shadow it | nothing, provided `--run-cwd` is given and that import lands in the repo (otherwise FAIL) |
| import from `--run-cwd` lands in repo | **cwd shadowing** — launching from another checkout's root imports THAT checkout | launch from the worktree under test, or use the console script |
| import with entry-script dir at `sys.path[0]` lands in repo | **script-dir shadowing** | move/rename the shadowing package next to the script, or pin+assert in the script |
| extra packages resolve in repo or venv | a sibling checkout is bleeding into the dependency | reinstall the dependency in this venv |
| which ogcore (version and install source) | WARN: a local build, not a release; or a build whose source folder is gone, which cannot be reproduced | record the branch and commit with the run, or rebuild from a release or a recorded commit |
| packaged parameters load (`--params-json`) | the JSON needs a different ogcore than the one installed | match the ogcore to the JSON, or the JSON to the ogcore, before launching |

Uncommitted changes are a WARN, not a FAIL — sometimes you *mean* to run dirty code. Say so out
loud before launching: "running with N uncommitted changes in <repo>."

## Judgment calls the script can't make

- **The branch check is only mechanical halfway.** The script prints branch+HEAD; *you* must
  confirm it's the branch the experiment is supposed to test. Compare against the task's intent,
  not against what's checked out.
- **Entry scripts for anything battery-grade should pin and assert**: `sys.path.insert(0, REPO)`
  then assert the resolved `<pkg>.__file__` is under `REPO` (pattern:
  `ogclews-link/experiments/run_battery.py`). The preflight catches a bad launch; the in-script
  assert catches a bad *re*-launch weeks later.
- **Run as a user would**: the documented CLI from the checkout's own env. If the preflight only
  passes under some ad-hoc invocation, the environment is wrong, not the preflight.
- **The checkout itself must come from OG-Core's official installer** (`scripts/install.sh`, see
  og-run). A GO on a hand-built environment (a worktree you made and `uv sync`ed, a conda env, a
  `PYTHONPATH` shadow) is not a GO for a reported run: install it properly and preflight that.
  Also confirm the entry script is the shipped example, unchanged (`git status` clean in the
  install), and that nothing is injected (`PYTHONPATH` unset, no `sitecustomize` on the path).
- **A GO is a precondition, not an authorization.** This skill never launches the run itself.
  A healthy baseline solve takes under ten minutes when run the way the example scripts run
  it, in parallel, with the Anderson solver (the model owner's rules, `../OG_RUN_RULES.md`); batteries are
  much longer, and every run is invisible while it runs. After a GO, propose the exact launch
  command with its expected duration and wait for the user's explicit go: long computations
  are never launched without one.
- **Contamination heuristic (post-run, standing):** if a fresh run reproduces a number from a
  known-buggy earlier run, assume the wrong code ran. Stop, re-run the preflight, and never
  commit or bless those outputs.
