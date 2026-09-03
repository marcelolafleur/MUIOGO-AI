---
name: muiogo-run
description: Run CLEWs/OSeMOSYS models in MUIOGO headless and collect their results — start and stop the server, solve one run or a batch, detect and diagnose failed solves, and save result CSVs reproducibly. Use when asked to run, solve, execute, or re-run a CLEWs case or scenario; to run several runs at once; to check whether a run succeeded or why it failed; or to collect the result files of a run. Also use when another skill needs a case solved first. For installing, importing or exporting a whole case or model, use muiogo-provision.
---

# Run CLEWs models in MUIOGO and collect results

Everything here goes through the `muiogo` command line, which drives MUIOGO's
HTTP API — the same path its web interface uses, so a headless solve and a
clicked solve produce identical results.

If you do not yet know where MUIOGO is installed, orient first with
`muiogo-ai status` (see the `muiogo-workspace` skill). Take all paths from there.

## Which world

Everything here acts on **one** world: the installed runtime, driven by
`muiogo-ai`. Use `muiogo-live` only if the user explicitly asked for their own
checkouts, and never bare `muiogo` — it can land anywhere. Every command prints a
`world:` line to stderr first; read it, and name that world when you report a
solve or a number, because the same run in the other world is a different number.
Exit code 3 means a command refused a world crossing: stop and say so, do not
sidestep it and do not switch worlds. Full rules: [../WORLD_DISCIPLINE.md](../WORLD_DISCIPLINE.md).

## The loop

```bash
muiogo-ai status                                   # is a server running? which cases exist?
muiogo-ai serve --detach                           # start one if not (backgrounded)
muiogo-ai cases                                    # exact case names — they contain spaces
muiogo-ai scenarios --case "CLEWs Demo"            # what runs already exist
muiogo-ai run --case "CLEWs Demo" --run REF        # generate input + solve
muiogo-ai results --case "CLEWs Demo" --run REF --out ./ref-results
```

`muiogo-ai run` regenerates the model input from the case's current parameter data
and then solves, so it always reflects edits you have made. It prints:

```
status: success
Result - Optimal solution found - Total time (CPU seconds):       1.06
```

## Starting and stopping the server

Start it detached — this is the headless default and it manages the process for
you:

```bash
muiogo-ai serve --detach     # backgrounds it, prints the pid and the log path
muiogo-ai status             # confirm: server  running — N case(s)
```

Stop it the same way:

```bash
muiogo-ai stop
```

**Stop with `muiogo-ai stop`, never by port.** It stops the exact process it
started, from a pidfile in the installation's own `servers/` directory. Killing
whatever holds a port — `kill $(lsof -ti :5002)` — can match an unrelated
process; that has actually happened. Run-state lives outside every checkout, so
a detached server never leaves untracked files in a model repository.

Two things to know. The port comes from the setup, and the two differ on
purpose: an installed muiogoai defaults to 5102, checkouts the user runs
manually keep MUIOGO's own 5002 — so a command can never silently drive the
wrong server. And a single `muiogo-ai run` occupies the server until it
finishes, so do not fire runs in parallel yourself; for several runs use
`muiogo-ai batch`, which solves them side by side on the server.

## Solvers

Use **CBC**, the default. It preprocesses the model input, builds the LP, and
solves. `--solver glpk` is broken in MUIOGO itself (it skips preprocessing and
fails on `MODEperTECHNOLOGY`) — tracked as MUIOGO issue #468. If a user asks for
GLPK, say it is a known upstream defect and use CBC.

Solve time scales with the model. The demo case takes about a second; a real
country case with many technologies, timeslices, and years can take minutes to
hours. For anything you expect to run long, propose it and let the user launch
it — that is an approval gate, not a formality.

## Running several

```bash
muiogo-ai batch --case "CLEWs Demo" --runs REF,CO2TAX,RETRG
```

The batch endpoint generates the solver input and solves the runs server-side
with CBC, several at a time: as many as the machine's cores and memory allow
(`MUIOGO_BATCH_WORKERS` in the server's environment overrides the rule; `1`
solves one after another). The solver input is rebuilt only when the model or
its data changed since the last run — the log says `reused` or `rebuilt` — which
saves a minute or more per run on a country model. The command reports total
elapsed time. It is the right tool for a scenario matrix. Verify afterwards — a
batch reports overall status, so check each run individually:

```bash
for r in REF CO2TAX RETRG; do
  echo "$r: $(muiogo-ai results --case "CLEWs Demo" --run $r | wc -l) result files"
done
```

## When a solve fails

A failed solve is not an exception you should swallow — it is the finding.
`muiogo-ai run` reports the failure and the solver's own message.

Check, in this order:

1. **The command's output.** The status line and solver message say most of it.
2. **The log**: `muiogo-ai log --case "<case>" --run <run>`.
3. **On disk.** Ask the world for the case path — never type a relative one:

   ```bash
   CASE="$(muiogo-ai case-path --case '<case>')"
   ls "$CASE/res/<run>/csv/"                # missing means the run produced nothing
   head -1 "$CASE/res/<run>/results.txt"    # raw solver output; first line is the status
   ```

Common causes and what they mean:

| Signal | Cause |
|---|---|
| `no value for MODEperTECHNOLOGY[...]` | GLPK path — switch to CBC (see above) |
| `Infeasible` / `problem is infeasible` | the model cannot meet demand under its constraints — a data problem, not a solver problem |
| `Unbounded` | a missing cost or capacity limit lets something grow freely |
| solver binary not found | GLPK/CBC not installed; `muiogo-ai status` shows solver availability |
| no results and no message | check the server log; the server may have stopped |

For infeasible or otherwise suspicious models, hand off to
`clews-model-review` (structure and data consistency) rather than guessing at
the data yourself.

## Provenance: making a number defensible

Every solve writes a `RUN.json` beside its results recording the objective, a
SHA-256 of the generated model input, a SHA-256 over all result CSVs, which
scenarios were active, the solver, and the MUIOGO version. You do not have to do
anything to get it; `muiogo-ai run` prints a one-line summary.

This matters because the pipeline is bit-deterministic but not self-auditing.
Solving the same run twice gives the same objective and byte-identical results —
but stored results can silently disagree with the case they live in. MUIOGO's own
demo ships a CO2TAX result of 600,590 tonnes that the shipped input data
reproduces as 513,337.

So, before you rely on a number you did not just produce:

```bash
muiogo-ai verify --case "<case>" --run <run>              # does the record still match disk?
muiogo-ai verify --case "<case>" --run <run> --resolve    # re-solve and prove it reproduces
```

`--resolve` re-solves and compares the objective and the results hash; it prints
"Reproduced exactly" or tells you the input data has changed. `muiogo-ai compare`
also warns on its own when a run in the comparison has no provenance record.

Rule of thumb: **if a comparison matters, every run in it should have been solved
by you, from the same input state.** Re-solve the ones that were not.

## Saving results reproducibly

```bash
muiogo-ai results --case "<case>" --run <run>              # list the result files
muiogo-ai results --case "<case>" --run <run> --out DIR    # download all of them
```

Results are one CSV per output variable in tidy long format — `NewCapacity.csv`
is `r,t,y,NewCapacity`; `AnnualTechnologyEmission.csv` is
`r,t,e,y,AnnualTechnologyEmission`. Dimension letters follow OSeMOSYS: `r`
region, `t` technology, `f` fuel, `e` emission, `y` year, `l` timeslice, `m`
mode, `s` storage.

When you save results for later analysis, make the directory self-describing so
the numbers can be traced back: name it for the case and run, and record what
produced it.

```
<somewhere>/<case>-<run>-<date>/
  csv/                     the downloaded result files
  RUN.json                 written automatically: objective, input and results
                           hashes, active scenarios, solver, MUIOGO ref
  NOTES.md                 which world you solved in, why you ran it, and what
                           you concluded
```

Never edit a file under `res/` by hand. Re-running a run deletes its previous
results first, so if a comparison matters, download before re-running.

## Handing off

- Interpreting, comparing, or charting what you just ran → `muiogo-analyze`.
- Creating a new scenario or combination to run → `muiogo-scenarios`.
- The model will not solve and you suspect its structure → `clews-model-review`.
- OG-Core solves are a different family entirely and are not run through
  `muiogo` — see `og-run-preflight` before launching one.

## Approval gates

Propose, draft, and prepare; the user decides. You may run short solves and save
results. Stop and ask before launching a long computation (propose the command
and expected duration), deleting a case or a run, or pushing, PR-ing, or merging
anything.
