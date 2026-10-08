# Tuning loop and environment

The run rules are in og-run-rules.md. When a solve misbehaves (a steady state that will not
converge, a transition-path resource-constraint error, a stall), use og-solver-diagnosis: it holds
the warm-start procedure, the RC_error triage by timing, and the pattern for running against an
unreleased ogcore. The short version for calibration work: suspect the cold-start seed before the
calibration, and do the RC_error triage before any tuning.

Contents
- Environment
- Run engineering: detail and evidence
- The in-model tuning loop
- Tuning-loop order: sourced parameters first
- Derived parameters regenerate together

## Environment

- **uv, not conda, through the official installer.** Install with OG-Core's `scripts/install.sh`
  (it runs `uv sync --extra dev` for you), then run the shipped example from that install
  (`../OG_RUN_RULES.md`). `AGENTS.md` is the source of truth for anything the installer does not
  cover; `docs/book/content/contributing/contributor_guide.md` is stale (still conda) in most
  repos. **[family]**
- **Never commit a `uv.lock` change from calibration work.** The lock is Dependabot-managed; if a
  local `uv sync` touches it, `git restore uv.lock`. Confirm `uv.lock` and `.python-version` are not
  in the PR diff. **[family among EAPD-DRB repos: PHL/ZAF/IDN/ETH; PSLmodels repos BRA/USA differ]**
- **Check the resolved ogcore in `uv.lock`, not the `pyproject.toml` floor.** The `ogcore>=` floors
  are not synced across repos, and the resolved versions differ too. To compare a repo with its
  siblings, grep `name = "ogcore"` in `uv.lock`. A parameter this skill relies on
  (`TPI_outer_method`, `r_gov_floor`, the `initial_guess_b_SS` family) may be missing from an older
  resolved ogcore; check with `hasattr` and treat an ogcore bump as its own change. A bump can also
  rename a parameter or change its shape, so load the packaged JSON against the new version
  (og-run-preflight `--params-json`) and fix what it rejects before running.
- **Preflight** (og-run-preflight): print branch + HEAD of every repo involved and `sys.executable`;
  assert imports resolve inside the intended checkout
  (`uv run python -c "import ogXXX, ogcore; print(ogXXX.__file__, ogcore.__file__)"`). Editable
  installs, script-dir shadowing and cwd shadowing silently run another checkout's code; this has
  caught real contamination. **[emerging: a house rule in OG-ETH's informality work; the full combo
  net-new]**
- **The example run is a smoke test, not a correctness check.** `test_run_example.py`
  (`@pytest.mark.local`) only checks the process is still alive after ~5 minutes; it never checks SS or
  TPI values. Numeric validation is the
  dashboard. **[family]**
- **CI-equivalent suite:** `uv run python -m pytest -m 'not local' -q`. **[family]**

## Run engineering: detail and evidence

The rules are in og-run-rules.md. The evidence behind them:

- **Why seven workers.** `SS.py` and `TPI.py` both call `client.submit` inside
  `for j in range(p.J)`, so workers beyond `J` idle. Seven is maximum parallelism when `J = 7` (the
  ports); OG-USA ships `J = 10`.
- **Why not a serial steady state.** Older measurements found the SS slower through the client than
  serial (~38s vs ~6s per GE evaluation **[JPN]**; 12+ min vs 66s **[PHL]**). They came from older
  ogcore, which re-sent the parameters to the workers on every evaluation. If the SS through the
  client is slow on a current ogcore, report it as a finding rather than building a serial driver.
  A two-phase hand driver (SS serial → pickle → TPI with the client) was used on PHL for speed; it is
  not the example pattern and is not used for official runs.
- **Why Anderson.** The M=1 PHL transition went from ~30–70 damped iterations (~20 min) to 11–12
  (~2–2.5 min) with monotonically falling distances **[PHL]**; OG-Core's own changelog reports a
  stiff multi-industry reform converging in 53 outer iterations vs 126 under constant `nu = 0.1`. It
  is TPI-only (it does nothing for a steady-state problem).

## The in-model tuning loop

**[PHL]** The tuning loop is cheap: use real solves, not algebra. A warm-guess SS solve takes
seconds, so *solve → read the revenue dashboard → adjust dials → re-solve* converges in 3–5
iterations for half a dozen simultaneous dials (GS φ2, `tau_c`, CIT adjustment, `p_wealth`,
`r_gov_shift`, `zeta_K`). Keep a small driver that loads the packaged JSON plus an overrides dict,
builds the same worker pool as the example script, calls `runner(..., time_path=False,
client=client)`, and prints model vs target by instrument. Two things it is not:

- not an official run: once the dials settle, fold the overrides into the JSON and run the example
  script through the client;
- not the last solve: always finish with a standalone solve of the packaged JSON itself (no
  overrides). It catches schema errors and seed problems the overrides path hides. If it fails, go
  back to the overrides you just folded in.

## Tuning-loop order: sourced parameters first

**[net-new: JPN]** The loop converges in 3–5 rounds only once the sourced parameters are settled. Any
change to a sourced parameter invalidates every tuned dial below it, because they were fitted against
the old base. Work in this order and expect one full retune per upstream correction:

1. sourced structurals: `gamma`, `delta`, `g_y`, the demographic window, spending shares;
2. tuned tax dials against the revenue targets;
3. `beta` against `K/Y`;
4. retune (2) if (3) moved the bases.

JPN took fourteen rounds because `gamma`, `delta`, `g_y`, `alpha_T` and the window were each
corrected after the tax dials were tuned. Audit the whole parameter surface before starting the loop,
not one parameter at a time. After any tax change, re-tune `zeta_K` (macro-open-economy.md).

## Derived parameters regenerate together

**[PHL]** Anything computed from demographics (the model-consistent `g_RM` path from `g_n`, the
`eta_RM` matrix from `omega_SS`) belongs in the demographics-regeneration tool, so a demographics
rebuild cannot leave it stale. Add a test asserting packaged value == constructor(packaged inputs).
