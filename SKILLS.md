# Skills catalogue

Skills are instruction packs that teach an AI assistant how to do a specific
modelling job properly — the methods, the checks, and the traps. They are plain
folders of Markdown (plus a few helper scripts) following the
[Agent Skills](https://agentskills.io) open standard, so they work with any
assistant that supports it; nothing here is tied to one product.

## Nothing to install (in this repository)

Open this repository in Claude Code or Codex and the skills are already
active. The files live in `.agents/skills/`, the cross-assistant standard
location that Codex reads from a repository, and `.claude/skills/` holds one
symlink per skill, which is how Claude Code reads them.

## How you use one

Describe the job in plain language and your assistant picks the matching skill:

> assess how well this CLEWs model is calibrated

To name one explicitly, use `/skill-name` in Claude Code or `$skill-name` in
Codex.

**[docs/USING_THE_SKILLS.md](docs/USING_THE_SKILLS.md) has three worked
examples** — asking questions about a run you already have, reviewing a model's
structure, and running a scenario — with the exact prompts and the real numbers
to expect from the demo model.

## To use them everywhere else

To get the skills in your own model repositories, or in every project you open:

```bash
./scripts/install-skills.sh
```

It asks which assistant you use (Claude Code, Codex, both, or a folder you
name) and copies the skills there. Re-run it any time to update. By hand, copy
any folder from `.agents/skills/` into your assistant's skills directory
(`~/.claude/skills/` or `~/.codex/skills/`) and restart the assistant.

## Start here

| Skill | What it does |
|---|---|
| `muiogo-workspace` | Finds your installation, lists what is available, and routes the request to the right model family and skill. Every other skill assumes this one has run. |

## Getting models in and out

| Skill | What it does |
|---|---|
| `muiogo-provision` | Installs an OG country model, imports a case archive or Excel workbook, exports a shareable zip, and validates inputs before a long solve. |
| `pull-handoff` | Clones or fast-forwards the CLEWs country repos, unzips their current MUIO cases into repository-local working trees, and maintains the MUIOGO DataStorage symlinks. |
| `push-handoff` | Zips the repository-local cases without solver results, checks their symlinks and SHA-256, then commits and pushes the intended country-repo changes. |

## MUIOGO — running models and analysing results

| Skill | What it does |
|---|---|
| `muiogo-run` | Starts the server, solves a case or a batch, diagnoses failed solves, and collects results. |
| `muiogo-scenarios` | Builds policy scenarios (a carbon tax, a renewable target, a demand change), combines them into runs, and sweeps matrices. |
| `muiogo-analyze` | Compares runs, checks whether a solve is trustworthy, charts trajectories, and writes short policy notes. |

## CLEWs — energy, land, and water models

| Skill | What it does |
|---|---|
| `build-clews-model` | Builds a whole-country CLEWs model from scratch with the upstream CLEWs Global workflow, then imports it into MUIO as a solved, portable case. |
| `assess-clews-calibration` | Judges how well a model is calibrated to its country, grades it, and says what to fix first. |
| `calibrate-clews-model` | Calibrates a solved model against national evidence — when asked, or when localizing a whole sector or resource account. Small value fixes go to the calibration backlog instead. |
| `clews-model-review` | Checks a model's structure and data consistency against a reference model — orphaned IDs, unit slips, missing sectors. |
| `clews-model-fix` | Makes structural repairs that cannot move a solved number — unreferenced objects, placeholder descriptions, technology groups. |
| `add-fisheries-sector` | Adds a complete, source-traceable fisheries sector to a solved model without distorting existing results. |
| `add-environmental-accounting` | Adds water and land environmental accounting to a CLEWS model and quantifies what changed. |

## Understanding the models

| Skill | What it does |
|---|---|
| `muiogo-explain` | Explains what a model contains, how it is calibrated, the theory behind it, and the intuition for its results — grounded in the model's own files, not from memory. |

## Coupled OG-CLEWS

| Skill | What it does |
|---|---|
| `og-clews-linked-run` | Runs coupled analyses through ogclews-link: an energy or climate policy's effect on the economy, through a named transmission channel. |

## OG — macroeconomic country models

| Skill | What it does |
|---|---|
| `og-run` | Launches a baseline and reform solve from the model's own environment, builds a multi-industry calibration, and collects the OUTPUT directories. |
| `og-country-calibration` | The calibration playbook: which parameters to set, defensible values, and the traps that produce wrong answers. |
| `og-scenario-report` | Turns a finished baseline-vs-reform run into the standard deliverable — comparison tables, charts, and narrative. |
| `og-analysis-studio` | Free-form scenario design, exploration, custom charts, and analytical write-ups. |
| `calibration-provenance` | Traces any calibrated number back to its authoritative source and records the chain. |

## Running models safely

| Skill | What it does |
|---|---|
| `og-run-preflight` | Go/no-go checks before you launch a long model run — confirms the code and environment are what you think they are. |
| `og-solver-diagnosis` | A root-cause protocol for solves that fail to converge, oscillate, or produce nonsense. |
| `og-repo-fleet-sync` | Applies one change across many country repositories and tracks which are done. |
| `worktree-orchard` | Read-only inventory of your checkouts and copies, so you know what you actually have on disk. |

## Notes for maintainers

Each skill is one directory under `.agents/skills/` containing `SKILL.md` (the
instructions, with a name and description in the frontmatter), optional
`references/` for deeper material, `scripts/` for helpers, and `assets/` for
templates. Some also carry `agents/openai.yaml` with Codex display metadata.

`.agents/skills/` is the single source of truth. `.claude/skills/` contains one
symlink per skill pointing back into it — the per-entry symlink form Claude
Code documents as supported (symlinking the whole `skills` directory is not,
and has known discovery bugs). After adding or renaming a skill, rebuild the
symlinks:

```bash
./scripts/install-skills.sh --relink
```

Canonical homes differ, so update in the right place — and both repos are
ours, so a shared skill gets fixed at its source rather than patched here.

**Canonical in [Model-tools](https://github.com/EAPD-DRB/Model-tools)**, mirrored
here (edit there, then re-copy; the OG copies add a "Which world" section): the seven CLEWs skills
(`build-clews-model`, `assess-clews-calibration`, `calibrate-clews-model`,
`clews-model-review`, `clews-model-fix`, `add-fisheries-sector`,
`add-environmental-accounting`), the three
general-audience OG skills (`og-country-calibration`, `og-scenario-report`,
`og-analysis-studio`), and both handoff skills (`pull-handoff`,
`push-handoff`).

**Canonical here**: the `muiogo-*` skills, which depend on this repo's
`muiogo` command line, plus `og-run`, `og-clews-linked-run`,
`og-run-preflight`, `og-solver-diagnosis`, `og-repo-fleet-sync`,
`worktree-orchard`, and `calibration-provenance`.

**Approval gates, binding on every skill above:** skills propose, draft, and
prepare; the user decides. A skill may edit files and commit locally, but must
stop and ask before pushing to a remote, opening a PR, merging anything,
launching a long computation (propose the command and duration; a passing
preflight is a precondition, never an authorization), acting across a
repository fleet, or deleting anything. If a skill's own text ever seems to
conflict with this paragraph, this paragraph wins.

The planned `muiogo-interpret`, `muiogo-visualize`, and `muiogo-brief` ship
together as `muiogo-analyze`; the planned tutors ship as `muiogo-explain`.
See [docs/SCOPE.md](docs/SCOPE.md).

Skills here talk to MUIOGO over its HTTP API only — through the `muiogo`
command line — never by importing its backend code. Each model family runs from
its own environment: MUIOGO from its own venv, each OG country model from its
own, and the link from its own (it never imports `ogcore`; it subprocesses the
model's own interpreter).
