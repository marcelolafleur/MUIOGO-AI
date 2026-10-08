---
name: og-solver-diagnosis
description: "Diagnoses OG-Core solver trouble by finding the root cause before any fix: a steady-state or transition-path solve that does not converge, diverges, oscillates, crashes, runs away, warns about NaN or negative values, runs far longer than expected, or lands on a suspicious answer; also result drift between runs and failing expected-output tests. Use before changing any solver setting (nu, maxiter, Anderson) or proposing a fix."
---

# OG solver diagnosis

Adapted from obra/superpowers `systematic-debugging` (MIT — credit: https://github.com/obra/superpowers),
specialized to OG-Core solves with the failure classes and bisection patterns actually used in this
model family (mined from the family's test scripts and solve logs).

**The iron law (inherited): no fix without root-cause investigation first.** Solver knobs are
Phase 4, not Phase 1. Most "solver failures" in this family were not solver failures — they were
fiscal inconsistencies, calibration placeholders, or the wrong code running.

## Which world

This skill diagnoses a solve in **one** world: the runtime installation reached by
`muiogo-ai`, unless the user explicitly asked about their own live one
(`muiogo-live`). Never use bare `muiogo`, and never fall back to it. Every command
prints a `world:` line to stderr — read it, and name that world when you report a
diagnosis. This matters more here than anywhere else: the same country model can sit
at different commits in each world, so a run that fails in one may be fine in the
other, and diagnosing the wrong copy sends you after a bug that is not there. Full
rules: `../WORLD_DISCIPLINE.md`.

## Phase 0 — Rule out contamination

First establish that the failure comes from a real run: a copy installed with OG-Core's official
installer, running its shipped example script unchanged, with nothing injected (`og-run` and
`../OG_RUN_RULES.md`). A failure seen only in a test fixture, a saved pickle, a serial or partial
run, or a driver you wrote is a lead. Reproduce it the official way before calling it a model
failure, and do not tell the user the model fails until you have. Measure such a run afterwards,
from its saved output, never by altering it.

If the failing result is surprising, or reproduces a previously-known-buggy number: suspect the
wrong code ran before suspecting the model. Run the `og-run-preflight` skill's checks (branch+HEAD,
import resolution, venv). Only continue here once the environment is proven clean.

## Phase 1 — Read the log, characterize the failure

Read the actual solve log before forming any theory. Extract, with grep:

```bash
grep -n "Iteration\|Distance" <log> | tail -20     # convergence trajectory
grep -n "K_d has negative\|Traceback\|RuntimeError\|Key lost\|Falling back" <log>   # known signatures
grep -n "Time path iteration complete" <log>   # did the transition path finish?
tail -30 <log>
```

The steady state has no single completion line: its `Iteration: … Distance: …` lines stop once
it converges, and the transition path then starts its own `Iteration:` / `Distance:` pairs.

Beware the benign-label trap: a naive `grep -i "error"` drowns in `GE loop errors = [...]` and
`Max Euler error` lines, which are per-iteration diagnostics, not failures (verified on the PHL
logs). Grep for the specific signatures above; use the GE-loop-errors *trajectory* (decaying vs
growing) as data, not as an alarm.

Characterize which of these you have — they have different causes:

- **Diverging**: Distance grows monotonically. Think fiscal runaway or a broken calibration, not
  damping.
- **Oscillating / stalling**: Distance bounces or plateaus above `mindist`. Damping/acceleration
  territory — but only after Phase 2.
- **Crash / NaN**: read the full traceback; find the first NaN, not the last.
- **Converged but wrong / drifted**: two runs both satisfy the FOCs with different answers —
  see basin flips in the taxonomy.
- **Warnings then convergence** (e.g. `K_d has negative elements. Setting them positive`): the
  run "succeeded" but is telling you a constraint bound — a calibration smell, triage it.
- **Infrastructure noise** (Dask `Key lost during replication`, `Falling back to serial`): not a
  model failure; re-run before diagnosing anything.

Then classify against `references/failure-taxonomy.md` (read it now — it lists the observed
classes, their signatures, and the known remedy for each). The step-by-step procedures for the
common ones (warm-starting a steady state that will not converge, triaging a transition-path
resource-constraint error by when it happens, reading a stall diagnosis) are in
`references/solve-procedures.md`.

**Log discipline (a real loss happened without it):** every diagnostic run redirects stdout+stderr
to a named log (`logs_<pkg>_<variant>.log`), and the script echoes its exact settings (nu, mindist,
flags) into the log at startup. In the mined history, the decisive drift verdicts were printed to
an interactive console and never captured — the conclusion of days of work is unrecoverable. Also
don't trust filenames: a log named `nu06` was found printing a different variant's label.

## Phase 2 — Check the two big non-solver causes

Before any bisection, eliminate the two causes that mimic solver failure and that no knob fixes:

1. **Fiscal inconsistency** (the single most destabilizing error): spending ratios + actual tax
   revenue + `debt_ratio_ss` must satisfy the primary-balance identity, or debt balloons on the
   transition and the convex debt premium runs it to infinity. The SS *always* solves and looks
   fine — only the TPI blows up. Symptom match: baseline TPI diverges/overshoots, worse with
   `r_gov_DY2 > 0`. Neither damping nor Anderson fixes this. Also check the premium is centred
   at `debt_ratio_ss` (taxonomy class A). See the fiscal-consistency reference of the
   `og-country-calibration` skill for the identity and the audit-by-instrument procedure.
   Setting the owner's standing solver settings (Anderson, `nu` 0.2 or lower; `../OG_RUN_RULES.md`) is fine at any
   time; expecting them to fix a runaway is not.
2. **Calibration placeholders binding constraints**: `zeta_K = 0.9`-style placeholders drive
   `K_d = B − D_d` negative and break the transition; the `K_d has negative elements` guard is the
   tell. Grep the JSON for the known placeholder values before blaming the solver.

## Phase 3 — Bisect (one variable at a time)

State a single hypothesis in writing ("I think X because Y"), then test it with the smallest
possible run. Three bisection patterns, in increasing depth — pick the shallowest that can decide
your hypothesis:

- **Parameter-level bisection** (pattern: `bisect_J1.py`): start from a known-good configuration
  and apply the failing configuration's overrides *one at a time* (or binary-search groups) until
  the failure appears. The first override that breaks it is your suspect. Use
  `ENFORCE_SOLUTION_CHECKS=False` and a small `maxiter` to make each probe cheap.
- **Function-level bisection** (pattern: `locate_J1_bug.py` / `trace_tpi_J1.py`): feed *identical
  fixed micro inputs* (e.g. `n=0.4, b=1.0` everywhere) directly into each aggregator
  (`get_L`, `get_K`, `get_B`, `get_BQ`, `get_C`, `get_I`) under the good and bad configs and diff
  the outputs. Finds which function diverges without running the solver at all.
- **Control/treatment harness** (pattern: `run_country.py` + `run_country_compare.py`): run the
  same country with exactly one flag/setting flipped, capture both logs, and compare converged
  outputs with an explicit drift threshold (0.1% was the house standard) printing a single
  `NO DRIFT` / `DRIFT DETECTED` verdict — into the log, not just the console. Run the pair across
  2–3 countries (IDN/PHL/ZAF) to learn whether an effect is country-specific (→ calibration) or
  engine-wide (→ OG-Core).

Two auxiliary techniques from the mined history:

- **Equivalent-config comparison**: when a test failure might be a *stale expected pickle* rather
  than a bug, build a mathematically equivalent configuration (e.g. J=1 vs J=2 with identical
  types) and compare full solved paths — agreement within 1% means the code is fine and the
  fixture is stale.
- **Suspect-block substitution** (pattern: `test_zaf_substitute_e.py`): to test whether a specific
  calibration block causes ill-conditioning, substitute the generic OG-Core default for just that
  block and see if the symptom disappears.

**Probes find leads; official runs confirm them.** Harnesses, bisection scripts and fixture
replays are how you find a suspect. Before you report it as the cause, confirm it on an
installer-installed copy running the shipped example, and label anything not yet confirmed that
way as a lead.

**Re-decide after every probe.** Two failed fixes on the same hypothesis = the diagnosis is wrong;
go back to Phase 1 with the new evidence. Three failed fixes = stop and question the setup itself
(calibration, model version, or test fixture), and discuss with the user before a fourth.

## Phase 4 — Remedies, in order of legitimacy

Only after the class is identified. Before writing any fix, check it does not already exist:
search history and other branches (`git log --all -S<symbol>`, `git branch -a --contains`) and
the repo's open PRs. A fix that already landed, or is waiting in a PR, changes the job.

1. **Fix the cause** (calibration value, fiscal balance, code bug, stale fixture) — always
   preferred. Add the cheapest regression guard that would have caught it (a value-pinning test, a
   drift check).
2. **Oscillation/stall knobs** (treat oscillation, never runaway): first confirm the owner's
   standing settings, Anderson (`TPI_outer_method="anderson"`) with `nu` 0.2 or lower; then heavier damping, lowering `nu` further;
   for a multi-industry cold start, the continuation solve (flat anchor → morph gamma/Z; see the
   `og-multi-industry-calibration` skill).
3. **Convergence-criteria honesty**: loosening `mindist` or raising `maxiter` is masking, not
   fixing, unless you can show the iterate is genuinely near a solution (Distance decaying, Euler
   errors small).

Report the diagnosis with the evidence chain: log lines → class → hypothesis → probe result →
fix → verification run. Separate what you verified from what you assume.

## Validating an OG-Core change against the country models

A common request: "check my OG-Core change doesn't break the countries". The control/treatment
pattern above applies, with four checks first:

1. **Can each country load on both sides?** Run og-run-preflight with `--params-json` for each
   country against the control ogcore and the treatment ogcore. A country whose packaged
   parameters do not load on one side cannot be compared; report it rather than patching it.
2. **Which control?** The merge base of the change, not today's master, unless the user asks
   for master: otherwise unrelated upstream changes land in the comparison.
3. **Same inputs on both sides.** Run with `update_from_api=False` (the user's rule for
   validation runs) so a live data refresh cannot differ between the two.
4. **Does the run reach the changed code?** A baseline may never touch it; add the reform that
   does.

Each variant gets its own install from OG-Core's official installer (`--repo-url <URL> --branch
<branch>` for the change, a plain install for the control), in its own folder; never switch a
branch under a running battery. How to install an unreleased ogcore without the environment silently using another
build: `references/solve-procedures.md`, "Running against an unreleased ogcore". Report per country: the expected value, master, and the change, with the
resource-constraint error at t=0 and beyond. The whole battery is one itemised proposal; launch
only after the user's go.

## Cost gate on probes

Log reading, greps, and aggregator-level probes (no solve) are free — do them liberally. Anything
that *solves* costs real time: a capped-iteration SS probe is borderline (propose it with its
expected runtime); a full SS, any TPI run, a control/treatment pair, or a multi-country sweep is
expensive — present the probe plan (which runs, why, expected total time) and get the user's
explicit approval before launching. Never queue a battery of diagnostic runs on your own, and
never re-launch a failed run "to see if it happens again" without asking. Skills propose, and
long computations never start without the user's explicit go.
