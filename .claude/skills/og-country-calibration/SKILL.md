---
name: og-country-calibration
description: >-
  Calibrate or refine an OG-Core overlapping-generations country model (OG-USA/PHL/ZAF/IDN/BRA/ETH
  and new ports), single- or multi-industry. Use when setting or reviewing macro/open-economy
  parameters (debt, zeta_K/zeta_D, g_y, remittances, aid, debt-elastic premium), the capital share
  gamma, the earnings e-matrix, demographics, chi_n, tax rates, informality, or a SAM-based
  multi-industry split; when porting the model to a new country; when validating a steady state
  against country data; or when the user mentions calibration, a country repo, a SAM/multisector
  build, or steady-state targets. Encodes the family's transferable methods, pitfalls, and house
  rules — methods, not one country's numbers.
---

# Calibrating an OG-Core country model

Transferable lessons distilled from the OG-Core country family (OG-USA, OG-PHL, OG-ZAF, OG-IDN,
OG-BRA, OG-ETH). This is a **method-and-pitfall playbook**, not a table of one country's values —
every number below is an *example*; you re-derive it for your country. Each item is tagged with
**provenance** so you know what is battle-tested vs. emerging vs. novel:

- **[family]** — done the same way across most/all repos.
- **[emerging]** — a good practice in only 1–2 repos (usually OG-IDN/OG-ETH); adopt and propagate it.
- **[net-new]** — not done in any repo yet; do it anyway because it prevents real errors.

Two reading rules:

- **Country tags are provenance, not scope.** `[ZAF]`/`[ETH]`/`[PHL]` record *where a lesson was
  learned and battle-tested* — the evidence trail — never *which country it applies to*. Every method
  here is on the menu for every country. Where applicability genuinely is conditional, the condition
  is a country **characteristic** stated in the item itself (agrarian/informal, aid- or
  remittance-dependent, distressed sovereign, rectangular vs diagonal make matrix) — never a country
  name.
- **Best effort on every block, graded honestly.** Most blocks have a ladder from minimal to ideal
  (flat → progressive → microdata PIT; narrative → structural informality; borrowed → re-tilted
  `chi_n`; naive → value-added `io_matrix`; direct solve → continuation). Calibrate each block at the
  **highest rung the country's data supports**; when the data isn't there, take the lower rung *and
  say so in the docs* — a documented fallback ("chi_n borrowed from OG-USA, uncalibrated") is a
  legitimate calibration, while an **undocumented placeholder is the pitfall half this file exists to
  prevent** (the 0.9 `zeta_K`, the flat 22% PIT, the stray bequest tax). Never let one block's missing
  data stall the rest of the calibration. And for every number — calibration input or validation
  anchor — **actively search for the most authoritative source that exists for this country**,
  starting with the official national institution that owns the number (see the sourcing hierarchy in
  Validation); named sources in this file are roles to search by, not a closed menu.

Always verify a claim against the **actual checked-out ref** of the repo in front of you — sibling
docs sometimes cite a *cousin repo's feature branch* as if it were canonical, and docs drift from
code. Open the file; don't trust memory or a sibling's citation.

## Which world

This skill acts on **one** world: the runtime installation reached by `muiogo-ai`,
unless the user explicitly asked for their own live one (`muiogo-live`). Never use
bare `muiogo`, and never fall back to it. Every command prints a `world:` line to
stderr — read it, and name that world when you report a result or a number. Worlds
hold different OG checkouts and different model registries, so the same country
model can exist in both at different commits. Locate the checkout you mean with
`muiogo-ai status` rather than assuming a path. Full rules:
`../WORLD_DISCIPLINE.md`.

## The mental model (read this first)

1. **The packaged `og<xxx>_default_parameters.json` is the source of truth.** `Calibration(p,
   update_from_api=False)` (the default) fetches nothing and overlays only no-op identity values
   (single-industry: `alpha_c=[1.0]`, `io_matrix=[[1.0]]`; empty for multi-industry) — `macro_params`
   and `demographic_params` are `{}` and `e` is `None`. A curated few parameters refresh only when a
   caller passes `update_from_api=True`. **[family]**
1b. **Anything you do not set stays AMERICAN — count what your `Calibration` actually delivers.**
   The highest-value question to ask of any port. OG-JPN delivered seven parameters; thirty-four
   mattered. The US defaults that bite hardest, and that no repo reliably overrides:
   `delta_annual` 0.05 · `beta_annual` 0.96 · `mean_income_data` **in US dollars** (it scales `factor`,
   so every tax function and the pension formula are evaluated at US income levels) · `pension_system`
   US Social Security · **`alpha_db` 0.0** (switching to Defined Benefits without it pays zero
   pensions) · `tax_func_type` `DEP` (US microdata) · `cit_rate` 0.21 (US federal) · `p_wealth` 0.0 ·
   `initial_foreign_debt_ratio`/`zeta_D` 0.4 · `debt_ratio_ss` 2.0 · the `initial_guess_*` trio.
   This is the concrete argument for the packaged JSON: it makes the whole surface visible at a glance,
   where a handful of Python functions makes everything unset invisible. **[net-new: JPN]**
2. **Most parameters are weakly identified alone.** The real test of a calibration is whether the
   **joint steady state** resembles the country's economy — validate the SS against a dashboard of
   data moments, not each parameter in isolation. **Lead that dashboard with fiscal data — it is the
   sharpest validator.** Tax collections by instrument (PIT / CIT / VAT+indirect as % of GDP), the
   debt ratio, its foreign share, and the effective real rate on debt are (a) **published precisely**
   by the treasury / revenue service / IMF, to the currency unit; (b) **convention-free** — they map
   one-to-one onto model ratios, unlike GDP / wage / consumption *levels* (arbitrary model units,
   need `factor`), sector *nominal* output shares (numeraire-distorted, never comparable), or `r`
   (genuine modelling latitude); and (c) **self-checking** via the government budget
   identity (see Fiscal consistency), so a miscalibration surfaces as an inconsistency in the SS and
   as an outright debt runaway on the transition. So a calibration that nails its fiscal ratios is
   validated on its most trustworthy *and* most stability-critical dimension. `factor` itself is a
   fiscal diagnostic — it sets the currency income at which the tax functions are evaluated, so a
   `factor` gap is a mis-collected-tax error, not a cosmetic one. Treat the production / preference /
   earnings moments (sector VA shares, hours, the Gini) as a necessary second tier that fiscal data
   can't speak to. **[emerging: IDN, ETH; the fiscal-first framing net-new: ZAF]**
2b. **`K_f/K` is a FIRST-tier moment: published, and a lever on `K/Y`.** It is on the dashboard
   list under Validation, yet the mental-model paragraph above once grouped it with `r` as
   "open-economy modelling latitude". **That contradiction is the actual defect** — the skill said
   both, so neither instruction bound, and JPN shipped `zeta_K` as a placeholder for fourteen tuning
   rounds. When two parts of a playbook disagree, the weaker one wins by default. `r` stays in the
   latitude bucket; `K_f/K` does not. **For the concept — and it is a sign-level trap, not a
   magnitude one — see "`K_f` is a net quantity" under Dashboard completeness before you pick a
   target.** **[net-new: JPN]**
3. **Single-industry first; multi-industry is a separate, non-destructive file** — its own JSON + its
   own example; the single-industry default keeps working untouched. **Two packaging choices, both
   legitimate — pick per repo, but never hand-write the file (always regenerate from the builder):**
   - *Lean overlay* **[PHL]**: the multisector JSON carries only the parameters that differ (`M`, `I`,
     the per-industry vectors, `alpha_c`, `io_matrix`, the chi conversion); the example loads the base
     JSON *then* the overlay. Pro: small reviewable diffs, and the economy-wide values live in one
     place so they can't drift. Con: **not standalone** — loading the overlay alone silently falls
     back to OG-Core (US-ish) defaults for everything it omits (a real footgun). It is tiny because
     ~97% of the base file is baked demographic arrays (`imm_rates`/`omega`/`rho`) it doesn't repeat.
   - *Self-sufficient file* **[ZAF]**: the builder merges base + multi-industry overrides and writes
     the *full* file, so it loads standalone in one step exactly like the single-industry default. Pro:
     matches the "one file = one calibration" expectation, no footgun. Con: it duplicates the base's
     economy-wide values (including the multi-MB demographic arrays), so it can **silently drift** from
     the base if the base is recalibrated and this file isn't regenerated. Mitigate with the discipline
     of regenerating on every base change (ZAF's choice), optionally backed by a drift-guard test
     asserting every non-multi-industry key equals the base — cheap insurance against a silent, hard-to-
     spot divergence, though some prefer to keep the test surface minimal.
   Never let the single-industry default carry multi-industry values, whichever you pick. **The
   deliverable per representation is exactly one thing loaded one way:** one self-sufficient JSON that
   carries every value the model needs + one example script (baseline + one representative reform),
   mirroring the single-industry `run_og_<country>.py`. Don't ship reform-variant example scripts
   (`*_cit_cut.py`, `*_energy_tax.py`, …) — a reform is a few lines the user edits in the one example;
   parallel scripts just rot and drift. **[family]**
4. **Calibrate effective, not statutory, quantities.** Wherever a large share of activity is
   informal/exempt/uncovered, the calibrated rate = actual collections ÷ the model-wide base, not
   the statutory rate. Apply this **consistently** across every tax instrument (OG-BRA is the
   counter-example — it discounts PIT for informality but leaves payroll at the full statutory rate).
   **[family]**

## Before you start: environment & preflight

- **uv, not conda.** `uv sync --extra dev`, then `uv run <cmd>`. `AGENTS.md` is the source of truth
  for setup — `docs/book/content/contributing/contributor_guide.md` is stale (still conda) in most
  repos. **[family]**
- **Never commit a `uv.lock` change from calibration work.** The lock is Dependabot-managed; if a
  local `uv sync` touches it, `git restore uv.lock`. Confirm `uv.lock`/`.python-version` are not in
  the PR diff. **[family among EAPD-DRB repos: PHL/ZAF/IDN/ETH; PSLmodels repos BRA/USA differ]**
- **Mirror the ogcore version via the resolved `uv.lock`, not the `pyproject.toml` floor.** The
  `ogcore>=` floor strings are NOT synced across repos; the EAPD repos have all converged on the
  same resolved version in the lock. To check "does this repo match its siblings," grep
  `name = "ogcore"` in `uv.lock`, not the floor. **[family]**
- **Model-run preflight — do this before every solve.** Assert the interpreter's imports resolve
  inside the intended checkout/venv (`uv run python -c "import ogXXX, ogcore; print(ogXXX.__file__,
  ogcore.__file__)"` and check the paths) **[emerging: documented as a house rule in
  OG-ETH.informality/INFORMALITY.md]**; and print branch + HEAD of every repo involved plus
  `sys.executable` **[net-new — no repo does the full combo]**. Editable installs, script-dir
  shadowing, and cwd shadowing silently run another checkout's code. This has caught real
  contamination.
- **Confirm before launching runs.** A steady-state solve is ~1–2 min; a full example (baseline +
  reform transition) is several minutes. Propose and let the user launch.
- **The example run is a smoke test, not a correctness check.** `test_run_example.py` (`@pytest.mark.local`)
  only asserts the process is still alive after ~5 min — it never checks SS/TPI values. Numeric
  validation is manual/docs-based (the dashboard). **[family]**
- **CI-equivalent test suite:** `uv run python -m pytest -m 'not local' -q`. **[family]**

## Macro & open-economy block

Method → pitfall → exemplar.

| Sub-block | Method | Pitfall | Exemplar |
|---|---|---|---|
| `start_year` | **A calibration decision, not a default: the most recent year the calibration can OBSERVE, not a projection year.** Check which anchors are observations vs extrapolations under each candidate year — the initial debt ratio is the sharp test (it must equal the debt ratio at the START of the start year, i.e. end of the prior year), and levels observed in year X (remittances/GDP, interest actuals) are data for a year-X start but extrapolations for X+1. Changing it regenerates demographics (and everything demographics-derived) via the country's regeneration tool, and re-maps the fiscal glide to the program years | Inheriting a future start year from a sibling repo: PHL shipped start 2026 while its latest data was 2025 — the packaged initial_debt_ratio 0.60 was in fact the beginning-of-2025 value (a 2026 start needed ~0.62), and the 2025-observed remittance ratio was being treated as a 2026 extrapolation | PHL (caught by the user, moved 2026→2025) |
| Debt | `initial_debt_ratio` is *measured* (national/IMF/QPSD series); `debt_ratio_ss` is a *policy anchor* (program target/stance), a separate parameter that shapes the whole SS | Leaving `debt_ratio_ss` inherited/undocumented; not checking whether a debt-ratio jump is a **valuation effect** (FX float revaluing external debt) vs. real deterioration | IDN, ETH |
| `zeta_D` | Default: set = `initial_foreign_debt_ratio` (assume foreign share of *new* issuance = foreign share of *stock*) | Using the realized flow when it's a crisis-period **outlier** (donor surge, debt standstill) — use the DSA's projected medium-term flow instead | USA measures the flow directly; ETH uses the DSA projection |
| `zeta_K` | It's a **marginal fill-share no dataset measures — calibrate it by the level it produces**: tune until the solved SS `K_f/K` matches the IIP foreign-capital share (2-3 SS solves bracket it; PHL sensitivity ≈ 0.4pp of `K_f/K` per 0.01 of `zeta_K`). The normalized Chinn-Ito index is the *prior* locating the plausible range, not the target. **Re-validate after ANY tax-side change** — tax recalibration moves domestic saving, which moves `K_f/K` at fixed `zeta_K` (PHL: honest taxes pushed 0.26→0.14; `zeta_K` 0.4→0.47 restored the 0.20 IIP anchor) | The **`zeta_K = 0.9` placeholder** ("implies high openness") — drives domestic capital `K_d = B − D_d` negative, binds `K_d ≥ 0`, and breaks the transition. Also: treating Chinn-Ito as the target and never solving for the level | Method: IDN, ETH; level-tuning executed on PHL. The 0.9 pitfall: IDN hit it and fixed it, PHL fixed it in #68 |
| `world_int_rate_annual` | **OPEN, investment-grade:** risk-free (~4%) + country sovereign spread. **NEAR-CLOSED/DISTRESSED:** leave at the ~4% benchmark and route country risk through low `zeta_K` + the debt-elastic premium instead | Adding a spread for a defaulted/restructuring sovereign (wrong model); or leaving it undocumented | IDN (open); ETH (distressed) |
| `g_y_annual` | **Measure per HOUR, not per worker.** Labour input is people × hours × ability and steady-state hours per worker are CONSTANT, so a trend in hours per worker is transitional and must be stripped — exactly like a trending participation rate, and the two must be treated consistently (easy to strip one and leave the other). PWT via FRED: real GDP ÷ (persons engaged × average hours). JPN 2000-2019: +0.557%/yr per worker, −0.472%/yr hours, **+1.035%/yr per hour** **[net-new: JPN]**. Then choose the growth window as **named constants** with a rationale (start after a structural break, end before the latest shock, reject unrepeatable booms). Critically, the SS is a **long-run** state, so `g_y` must be **consistent with the growth the `debt_ratio_ss` anchor assumes** (`GDP growth ≈ g_y + g_n_ss`): if the debt target is a country's stabilization *plan* built on a medium-term recovery, use that recovery's productivity growth (`= medium-term GDP growth − g_n_ss`), not the stagnant realized window | Naive "all history"/inline date arg; **or realized-stagnation `g_y` paired with a stabilization `debt_ratio_ss`** — internally inconsistent (that's the *pessimistic, debt-drifts-up* scenario), so the model's debt won't actually hold at the target | IDN, ETH, PHL. ZAF: realized 0.6% was inconsistent with the 0.765 anchor's ~1.8% growth → raised `g_y` to ~1.4% (= 1.8% − g_n 0.42%) |
| `r_gov` base wedge (`r_gov_scale`, `r_gov_shift`) | `r_gov = scale·r − shift + premium`, and it multiplies the **whole debt stock** in `debt_service = r_gov·D` — so it is an **average/effective** real rate. Keep the LMWW **slope** (`scale`, the estimated sovereign-vs-corporate pass-through), but **re-anchor the `shift`** so the SS `r_gov` equals the country's actual real *effective* rate on debt = interest payments/gross debt (take BOTH from the treasury's own cash-operations/budget report — news stories mislabel fiscal years; PHL's widely-quoted "FY2024" interest figure was actually FY2025) minus expected inflation. **Expect `r_gov < g` for many EMs** — then the debt-stabilizing primary balance `pb*` is a *deficit*, matching how such countries actually stabilize debt ratios while running primary deficits; and state the **consolidation gap** (actual primary balance vs `pb*`) explicitly in the docs, since the stable-debt SS embeds it | The LMWW **intercept** is a cross-country EM average that maps a *nominal USD bond-yield* level onto the model's *real* MPK — it over-predicted ZAF by ~0.5–0.6pp and **PHL by ~3pp** (5.1% vs the ~2.0% the Treasury pays), inflating the debt-stabilizing primary surplus and forcing spending too low. Don't use the 10-yr/ILB *marginal* yield either — that's new-issue cost, not the stock average | ZAF (~3.7%), PHL (~2.0%, `calib/remittances`); IDN/ETH still ship the raw LMWW intercept |
| Remittances `alpha_RM_1`/`alpha_RM_T`, aid `alpha_FA` | Hand-set JSON values, **never fetched**. **Level:** use the *personal* (BPM6) remittance measure — the model's `RM` is household income from abroad — central banks often headline a GDP ratio only for the narrower *cash* (formal-channel) series, ~1pp of GDP lower; derive personal/GDP on one consistent denominator. **Path:** `alpha_RM_1 = alpha_RM_T` pins only the endpoints — `get_RM` compounds `(1+g_RM)/(e^{g_y}(1+g_n))`, so a flat RM/Y **requires `g_RM[t] = e^{g_y}(1+g_n[t-1]) − 1`, a time-varying path** (no scalar works when `g_n` moves; regenerate it with the demographics). `g_RM` is in model growth units — never the nominal-USD growth rate from a press release. The SS never reads `g_RM` (`RM_ss = alpha_RM_T·Y`), so a wrong path corrupts *only* the transition. **Distribution:** ogcore's default `eta_RM` is population-proportional; survey evidence (FIES-type) shows remittance value concentrated at the top. Build group shares as quintile mean income × remittance-share-of-income (equal-count quintiles ⇒ value share follows directly), map to the J groups by interpolating the cumulative distribution, spread per-capita over ages; note the current-vs-lifetime-income ranking caveat (overstates concentration) vs uniform-within-top-quintile (understates it). **Schema: `eta_RM` in the parameters JSON is (S,J)** — the (T+S,S,J) on a live Specifications object is internal tiling | A nominal growth rate in the `g_RM` slot: PHL shipped `g_RM = 0.03` (Dec-on-Dec USD growth) against a ~5.7% model-consistent denominator — RM/Y silently fell 35% below its calibrated share by t≈24, recovering only after t≈100, with nothing in the docs intending it. And the cash-measure trap: PHL's 0.072 came from a BSP headline that was the cash series (personal was 8.1%) | PHL (all three, fixed on `calib/remittances`); ETH (aid) |
| Debt-elastic premium `r_gov_DY`/`r_gov_DY2` | The base wedge is a **country-agnostic** OLS inversion of Li-Magud-Werner (same numbers everywhere). Add the convex Schmitt-Grohé/Uribe term in **centered** form around `debt_ratio_ss`, expand, fold the constant into `r_gov_shift` → premium is **exactly zero at the SS target**, so it only prices transition overshoot: `r_gov_DY = -2·r_gov_DY2·D̄`, `r_gov_shift = base − r_gov_DY2·D̄²` | A live-refresh path that returns the *raw* LMW shift silently **de-centers** the premium and moves the SS — freeze it | IDN, ETH |
| `initial_Kg_ratio` | Solve the model's own SS law of motion `K̄g/Ȳ = (1−φg)·αI / (e^{gy}(1+gn) − (1−δg))`; if the *measured* stock is far above sustainable (SOE-built boom), **start at the measured value and let it depreciate** | Inheriting the sibling-shipped `0.2` undocumented when `gamma_g > 0` (OG-Core's own default is `0.0`; PHL/ZAF/IDN/BRA all ship `0.2`, but only PHL has `gamma_g>0`, so elsewhere it's inert) | ETH only — replicate wherever `gamma_g > 0` |
| Initial household wealth `initial_wealth_ratio` (**OG-Core #1189 — not in 0.19.0; if your resolved ogcore predates the merge, install from the PR branch**) | **Diagnose first**: without the parameter (OG-Core pre-#1189, or left at the 0.0 default), the transition imposes the SS wealth profile rescaled so aggregate B(0) = B_ss. Compute the implied per-household scale `B_ss / get_B(b_sp1, p, "SS", True)` — it measures the demographic distance between the initial and stationary populations, and anything far from 1 hands every initial household a uniform windfall (young population) or confiscation (old), which short-horizon retirees rationally consume/absorb: the fingerprint is a violent year-1-or-2 aggregate consumption spike concentrated in ages 60+ across all j, an investment collapse, a tau_c revenue pulse, and a spurious debt paydown (or the mirror images). **Fix** (`initial_wealth_ratio` arrives with OG-Core #1189 and is **not in 0.19.0** — `Specifications` has no such attribute there, so check your resolved version and install from the PR branch if needed; **the diagnostic below does not depend on it** and should be run either way): set `initial_wealth_ratio` (OG-Core #1189; wealth-to-GDP at t=0 — the anchor is STATIC within the solve because initial wealth is a predetermined state: rescaling households' initial wealth between outer-loop iterations, even damped, drives the initial cohorts into infeasible negative-consumption roots that satisfy the extended FOCs AND pass ogcore's constraint checker, which watches a different object — always read min household consumption from the pickle) from data: `(K/Y_PWT − public capital stock/Y_ICSD) × (1 − IIP foreign-owned share) + domestic-held share × D/Y`. Compute the PWT ratio from the raw current-PPP series pair (capital `CKSPPP…` over output `CGDPOS…` on FRED), never from memory — PHL moved 3.33 (2019) → 3.97 (2023). Cross-check against household-net-worth estimates (UBS databook class — expect them LOWER; they undercount EM real property) and expect initial < SS wealth ratio for a fast-growing EM (a converging-up economy). **Out-of-sample check + a tension to expect:** the initial-period foreign capital share K_f(0)/K(0) vs the IIP is untargeted and worth reporting — but where the model's K/Y overshoots the PWT (the family trait), measured household wealth and the measured foreign share CANNOT both be hit (the model fills its larger capital stock with foreign inflows). Keep the household-wealth anchor (it is the quantity the parameter IS) and document the foreign-share miss with its mechanical cause; hitting the IIP share instead would need initial wealth far above any measured household-claims construction (PHL: 4.3 vs 3.35). **Then re-tune the `alpha_G` glide under the new initial condition** — it was fit against the windfall-distorted revenue path | PHL scale factor was **1.625** (63% windfall): retirees consumed at 3–7x SS for years, C jumped 41% for one year, I_d → ~2% of long-run, debt paid down to 50% vs a 60% target — all invisible in reform-minus-baseline tables (both paths share the initial condition), so it survived every reform validation and surfaced only in level exercises. Note the model *forces* B(0) = K_d(0) + D_d(0), so the capital-side data construction IS the model-consistent measure — don't reach for household balance-sheet surveys first | PHL (diagnosis + fix, OG-Core #1188/#1189) |

### Macro rows added since the table above (same columns)

| Sub-block | Method | Pitfall | Exemplar |
|---|---|---|---|
| `delta_annual` | **Source it; no repo does.** `delta = (CFC/Y)/(K/Y)` — consumption of fixed capital from World Bank `NY.ADJ.DKAP.GN.ZS` (convert the GNI basis to GDP), `K/Y` from PWT. Decisive in a **slow- or negative-growth** economy: steady-state investment is `(g + delta)·K/Y`, so as `g → 0` depreciation is nearly the only thing generating investment demand | Leaving OG-Core's 0.05, a US value. JPN 0.05 → 0.062 moved investment 2.7pp of GDP | **[net-new: JPN]** |
| `beta_annual` | Not observable — calibrate to the **capital-output ratio**. The firm FOC (`firm.get_r`, Cobb-Douglas) is `K/Y = (1-tau_b)·gamma / (r + delta - tau_b·delta_tau - inv_tax_credit·delta)` — write it in full, because the tax terms are not small (on JPN they move the numerator 14% and the denominator 3.5%) and an approximate `gamma/(r+delta)` will send you after the wrong lever. With `gamma` and `delta` sourced, `K/Y` is a function of `r`, and `r` is what `beta` moves; 2–3 SS solves bracket it. **`beta` is one of ELEVEN levers on `K/Y`** — see Step zero before concluding it is the binding one. **Order matters:** sourced parameters FIRST, then look at `K/Y` — if it already sits on the PWT value `beta` has no room and moving it is curve-fitting; if `K/Y` is off, `beta` is the right instrument | Leaving OG-USA's 0.96 unexamined, or moving `beta` while `K/Y` is already on target. Re-ask after ANY change to `gamma`, `delta` or `g_y` — on JPN the answer flipped twice | **[net-new: JPN]** |
| `alpha_T` | **CASH transfers only.** Health, long-term care and education delivered IN KIND are *government final consumption* in the national accounts; in OG-Core they belong in `G`, which stays out of the household budget — not `TR`, which enters it. Split from OECD SOCX or the national social-security accounts | In-kind spending in `alpha_T` hands households income they do not have and inflates consumption directly. JPN shipped 0.075 against a true cash ~0.025 — 3x too high, the largest single error in its consumption fit. Worst wherever health care is publicly provided in kind, i.e. most of the OECD | **[net-new: JPN]** |
| `r_gov` floor | ogcore wraps the wedge in `np.maximum(..., 0.00)` (`fiscal.py:get_r_gov`). A sovereign in a sustained negative-real-rate regime is silently clipped; the tell is a reported `r_gov` of exactly `0.0000` when the formula returns negative | It does not distort the interest bill — it distorts `pb*`, hence government spending. Measured on JPN: **0.51pp of GDP**. Report upstream; do not compensate elsewhere | **[net-new: JPN]** |

## Capital share (gamma)

- **Baseline [family]:** `gamma = 1 − labor_share` (ILOSTAT/national accounts), then carve `gamma_g`
  (public capital share) out of the *capital* side. Fine for formal economies (USA).
- **Gollin / self-employment adjustment — for agrarian/informal economies.** Raw labor shares are
  biased because self-employed mixed income is booked as capital. Two distinct methods:
  - *Aggregate triangulation* **[ETH]**: adjust the economy-wide labor share up using non-circular
    evidence — a growth-accounting check `gamma = (r+δ)(K/Y)` (an implausible implied return flags a
    wrong share), the Gollin direction-of-bias argument, and country institutions (e.g. state-owned
    land). State the result as a *range with a center*, not a point estimate.
  - *Cross-sectional rescale* **[multi-industry; PHL feature branch]**: keep the SAM's per-industry
    *dispersion* but rescale so the value-added-weighted mean equals the economy-wide capital share.
- **PITFALL [ETH, verified]:** the `update_from_api=True` path recomputes the **naive** `1 − ILOSTAT`
  and will **silently clobber** a hand-triangulated gamma (e.g. overwrite 0.30 with 0.515), undoing
  the whole firms.md argument. **Remove such curated structural params from the live path entirely**
  (as IDN did) — an `if update_from_api` guard is not enough.

## Earnings (the e ability matrix)

- **Method [family: PHL/IDN/BRA/ETH]:** reuse OG-USA's calibrated `e` matrix as the base and apply a
  **single-scalar exponential tilt** `e_country = e_USA · exp(a·e_USA)`, solving the one scalar `a`
  (bisection) so the model Gini matches the country's target Gini. One number per country, no bespoke
  data collection.
- **The method has TWO halves and the repos ship one.** EAPD-DRB/OG-ZAF#18 specifies (1) an
  **age-shape** adjustment from NTA income-by-age and (2) the Gini tilt above; #63 tracks getting (1)
  into the country repos. Shipping only the tilt leaves the *US* age profile in place — wrong wherever
  the country's age-earnings shape differs structurally (seniority pay, mandatory retirement,
  informality). Japan's factor is 1.09 at 55 and 0.62 at 65; peak earnings age moves 61 → 57.
  **NTA has no API**: establish a session, POST the query to `/web/nta/download-confirm`, then POST the
  session-scoped download form it returns **with a `Referer` header** (403 without one). The US is
  `"US"`, not `"United States"`. Both countries must come from NTA on the same variable and variable
  type — national wage surveys are not comparable to NTA levels. Normalise each profile over prime
  working ages before taking the ratio, and cap it at high ages where both approach zero.
  **[net-new: JPN]**
- **Do NOT use the ZAF-style hardcoded-coefficient method** (`get_e_orig`, WID-then-NTA two-step with
  hand-tuned arctan extrapolation) — it needs bespoke per-country re-derivation and isn't a drop-in.
- **Gini-concept trap [issue #33; family-wide risk]:** the target-country Gini and the US reference
  Gini (`gini_usa_data`) **must be the same welfare concept**. Mixing a World Bank PIP Gini
  (consumption-based for many developing countries) against the **World Bank income-concept US anchor
  (`gini_usa_data = 41.5`, WB SI.POV.GINI)** systematically understates the target's inequality. Use a
  matching concept for both (e.g. WID income) and check the docstring default matches the code.
- `lambdas` (lifetime-income groups, J=7) are byte-identical **across the country ports
  (PHL/ZAF/IDN/BRA/ETH)** and never re-derived — only the tilt `a` changes; OG-USA is the J=10 source
  the ports interpolate down from. `factor` is **solved endogenously in the SS**, not a calibration
  input.

## Demographics

- **Method [family]:** the shared `ogcore.demographics` module — fertility/mortality from the UN
  Population Division API, infant mortality taken from the UN age-0 mortality rate (same UN WPP
  series), **immigration solved as the residual** that reconciles consecutive UN population
  distributions (appropriate when immigration data is weak).
- The only per-country input is `country_id` (UN M49 code). **Use a single named constant**
  (`UN_COUNTRY_CODE`) referenced at both call sites — not an inline literal. **[safer: PHL/IDN/BRA]**
- **PITFALL [ETH, regressed twice]:** `calibrate.py` gets refreshed by copying a sibling repo, and the
  hardcoded `country_id` literal was wrong (710=South Africa instead of 231=Ethiopia) — twice, because
  a wholesale file copy forgot to swap it. **Add a regression test** asserting `country_id` matches the
  country being calibrated.

- **THE DATA WINDOW SILENTLY SETS THE LONG-RUN GROWTH RATE — currently wrong fleet-wide.**
  `get_pop_objs` holds fertility, mortality and immigration constant at `final_data_year`. Every repo
  passes `start_year + 1`, so the model sees **two years** of UN data and then frozen rates forever
  (ogcore's own default, `start_year + 2`, is barely better). Where projected demographic change is
  the point of the exercise this decides the answer. On Japan, widening from 2 to 74 years moved
  `g_n_ss` from **−1.070%/yr to −0.463%** and `pb*` from a surplus to a deficit.
  **The check:** compare the model's `g_n_ss` against the UN projection's own implied CAGR. A value
  well outside it is a too-short window, not a demographic fact. Use the **terminal** UN rates: the
  steady state is a long-run object, so a mid-transition snapshot is a category error. UN WPP ends at
  2100 and ogcore asserts beyond `start_year + 74`. **[net-new: JPN — worth a fleet sweep]**
- **A finite window leaves a discontinuity, and ogcore adds a second one.** Where the rates freeze,
  and again at `fixper = int(1.5 * S)` (period 120 for S=80) where ogcore *replaces* the population
  distribution with its fixed steady-state one in a single period, the transition's resource
  constraint breaches. On JPN, 318 of 320 periods satisfied `RC_TPI` with a median residual of
  7.96e-08; the two that failed were exactly those periods. `fixper` is invariant to any country-side
  setting — report it upstream rather than tuning around it. **[net-new: JPN]**
- **Cache the processed arrays.** ogcore refetches the whole UN series on every call and never reads
  its own `download_path` back. At a wide window that is ~100s per solve, and hammering the endpoint
  makes it fail intermittently — whereupon ogcore falls back to the offline mirror and the run dies
  with `KeyError: '<country_id>'`, naming the wrong cause. **[net-new: JPN]**

### Income-differentiated demographics (ogcore >= 0.18.0)

- `get_pop_objs()` accepts `income_percentiles` (pass the model's own `lambdas` — it is not data),
  plus `fert_gradient`, `mort_gradient`, and `infmort_gradient`: fertility and mortality tilted
  across the lifetime-income groups instead of identical across J.
- **The measured gradients live in
  [EAPD-DRB/Demographic-Gradients](https://github.com/EAPD-DRB/Demographic-Gradients)** — DHS
  fertility (TFR) and infant-mortality (IMR) tilts for ~78 countries, census household-deaths
  adult-mortality tilts for 14, and a GNI-keyed general fallback for everyone else. It plays the
  role for demographic *differentials* that Population-Data plays for *levels*; reference data by
  raw URL.
- **Before using it, fetch and follow that repo's AGENTS.md**
  (`https://raw.githubusercontent.com/EAPD-DRB/Demographic-Gradients/main/AGENTS.md`) — it maps
  each ogcore input to a file, states precedence, and lists the traps. It is the source of truth;
  don't work from a copy of its rules.
- **Check the country is actually in the library first.** It covers 78 developing countries and its
  AGENTS.md is explicit that the income-based fallback is valid only between $200 and $10,000 GNI per
  head — *"high-income countries are out of scope, not missing: do not extrapolate to them."*
  Extrapolating can reverse the **sign**: in high-income countries the fertility gradient often runs
  through marriage rates rather than family size. Leave them unset, say so, and pin the decision in a
  test so it is not later "fixed" as an oversight. **[net-new: JPN]**
- The two rules that change results, worth knowing before you even fetch: **divide the library's
  tilt by 100** (it is per unit wealth rank; ogcore wants per centered percentile point — getting
  this wrong is a silent 100× error), and **a country's own measurement beats the general
  gradient** — always state which route was taken and the survey/census year.

## Pensions

OG-Core supports `"US-Style Social Security"` (the default), `"Defined Benefits"`,
`"Notional Defined Contribution"` and `"Points System"`.

- **Leaving the default applies the US benefit formula in US dollars** — AIME bend
  points, PIA rates — to earnings scaled by `mean_income_data`, itself a US figure.
  A pension result from an uncalibrated port is arithmetic, not validation.
- **`alpha_db` defaults to 0.0.** Switching `pension_system` to `"Defined Benefits"`
  without setting it silently pays **zero pensions**.
- For a DB system `yr_contrib × alpha_db` **is** the gross replacement rate, so the
  parameter is directly observable — but OECD replacement rates are **old-age only**,
  while a country's pension spending also funds survivors' and disability pensions
  that OG-Core's single block cannot separate. Expect to carry roughly
  `OECD rate × (1 + survivors&disability share)` — about 15% more for Japan.
- `alpha_db` is sensitive to assumed productivity growth, since OG-Core averages the
  last `avg_earn_num_years` of earnings. Check the growth the OECD's own pension
  modelling assumes (1.25%/yr) against yours.
- Set `mean_income_data` in local currency, and `avg_earn_num_years` to the country's
  actual convention (career-average vs final-salary).

Validate against **public pension expenditure as a share of GDP**, not against the
replacement rate you fed in. **[net-new: JPN]**

## Labor supply (chi_n)

- **Honest default state [family]:** `chi_n` (the 80-age disutility-of-labor profile) is
  **byte-identical to OG-USA's values in every country repo — never recalibrated to any country's own
  labor data.** The estimation machinery is broken or absent everywhere (USA's is commented out; most
  repos have no `labor.py`; ETH's `labor.py` is orphaned ZAF QLFS code with a missing
  `estimate_chi_n` module — see issue #71).
- **So: treat "chi_n = borrowed from OG-USA, uncalibrated" as the default state of any port, and say so
  explicitly** — never present it as calibrated.
- **Before assuming the borrow is harmless, check total labour input per working-age person against the
  US** (hours/worker × employment rate). Japan is within 1% — 10.5% fewer hours offset by a much higher
  employment rate — which makes the borrow defensible rather than merely conventional. A country far
  off that ratio has a real problem. **[net-new: JPN]**
- To actually calibrate it: either (a) a single-scalar re-tilt analogous to the earnings Gini trick,
  matching an aggregate hours or labor-force-participation target; or (b) wire the country's labor
  force survey through a rewritten `labor.py` + a real `estimate_chi_n.py`.

## Taxes & informality

- **The universal method:** every effective rate = collections ÷ base. Apply it to PIT, `tau_c` (VAT),
  CIT (via `adjustment_factor_for_cit_receipts` × `c_corp_share_of_assets`), and `tau_payroll`
  (statutory rate × covered share of the *wage bill*, not headcount — or directly: SSC collections ÷
  the model's labor share of income). **Apply consistently** — OG-BRA
  is a cautionary tale: it discounts PIT for informality but leaves payroll at the full statutory rate.
- **`tau_payroll` is ADDITIVE on top of the ETR function** (`income_payroll_tax_liab = T_I + T_P` in
  ogcore `tax.py`), and with `frac_tax_payroll = 0` the combined take reports on the *iit* line while
  the payroll line shows zero — so a statutory payroll rate silently collects on the whole wage bill
  *in addition to* the income-tax function, invisibly. PHL: `tau_payroll = 0.14` was collecting a
  hidden 5.8% of GDP on top of a flat 20% ETR. Audit the **combined** household take, decompose it
  yourself (`true payroll = tau_payroll × wL/Y`), and set `frac_tax_payroll = SSC/(SSC+PIT)` so the
  reported split matches the data split. **[PHL]**
- **Standing check — statutory-for-effective on the bequest tax, now a THIRD family instance** (ZAF
  `tau_bq = 0.2` collecting 3.9% of GDP; PHL `tau_bq = 0.06` collecting 1.19% vs actual estate+donor
  collections of ~0.07%). Deductions, exemptions, and non-filing put effective estate taxation one to
  two orders of magnitude below statutory nearly everywhere: always compute `tau_bq` from
  collections ÷ model bequest flows, and grep every new port for this parameter. Check IDN/ETH/BRA.
- **PIT functional form — three paths, in increasing fidelity:**
  1. *Flat `linear`* ("given limited data"): a single ETR + MTR number. Cheapest, no progressivity.
     PHL/IDN/BRA pick the number; only ETH *derives* it (revenue identity). Fine as a first pass.
  2. *Progressive parametric form fit to the statutory schedule* **[ZAF — the best data-poor
     option]**: genuine progressivity with **no microdata** — you only need the country's statutory
     PIT schedule plus a collections target. Strongly prefer this over flat-linear whenever a
     statutory schedule exists (i.e. almost always). **Default to the GS (Gouveia-Strauss) form, not
     HSV.** GS floors the ETR at exactly zero — faithful wherever a statutory threshold + rebates
     exempt the bottom (most schedules), and numerically robust. HSV's ETR goes *negative* below the
     threshold, and that implicit bottom-end subsidy is **not cosmetic: on ZAF it drained transition
     revenue and helped push the TPI into a debt runaway, where GS with the same targets converged.**
     Recipe below.
  3. *Microdata-estimated nonlinear* (OG-USA via Tax-Calculator): a 12-parameter form fit by
     age×year to microsimulated ETR/MTR. Only feasible with a Tax-Calculator-equivalent + filer
     microdata.
- **Progressive-fit recipe (verified against ogcore `txfunc.py`).** Both forms calibrate the same
  way — the statutory schedule pins the *shape*, the collections target pins the *level* — and both
  use the *same* parameter triple/pair for `etr_params`, `mtrx_params`, `mtry_params` (analytically
  consistent; mtrx = mtry, the total-income MTR):
  - **GS** (`tax_func_type = "GS"`, params `(φ0, φ1, φ2)`): tax `T(y) = φ0·(y − (y^−φ1 + φ2)^(−1/φ1))`
    on total income. ETR = 0 exactly at the bottom and asymptotes to `φ0` at the top — so set
    **`φ0` = the statutory top marginal rate** (an anchor, not a fit), fit **`φ1`** (curvature) to the
    schedule's shape, and tune **`φ2`** (scale) in-model to the PIT/GDP collections target — the
    effective-rate/informality wedge enters here, pulling the level down to actual collections.
    (ZAF: `[0.464, 1.39288, 1.43e-8]` → PIT 10.1% of GDP, top MTR 45%. PHL: `[0.35, 1.196, 1.9e-8]`
    → PIT 3.12% of GDP.) Tuning mechanics **[PHL]**: the revenue response to `φ2` is **concave** —
    top incomes sit in the saturated region where ETR ≈ φ0 regardless of φ2, so halving φ2 cuts
    revenue by less than half; expect 2–3 in-model iterations, not one proportional step. Lowering
    φ2 for informality acts like shifting the schedule toward higher incomes — the right shape for
    "most earners effectively untaxed". And GS's smoothing means the sub-threshold ETR is *near*
    zero, not zero (PHL: ~1.2% at 80% of the exempt threshold) — accept it; it is the price of never
    going negative like HSV, and pin it in a test as a bound, not an equality. Incomes are evaluated
    in currency units via `factor` (`mean_income_data`), so φ2 carries units `income^(−φ1)`.
  - **HSV** (`tax_func_type = "HSV"`, `λ = coef0`, `τ = coef1`): `ETR = 1 − λ·y^(−τ)`,
    `MTR = 1 − λ(1−τ)·y^(−τ)`. τ (progressivity) is scale-invariant — fit it to the schedule's shape;
    λ absorbs the income scale — tune it to collections. (ZAF's HSV fit: τ≈0.14 tracked SARS — before
    the GS switch.) **Use only where a bottom-end subsidy is harmless:** below the tax threshold HSV's
    ETR goes negative, and in a tightly-balanced fiscal block that subsidy bleeds transition revenue —
    it contributed to a TPI debt runaway on ZAF. If the budget has no slack, use GS.
- **Informality — the maturity ladder** (choose the rung the data supports):
  1. *Narrative only* **[BRA]**: name informality as the reason effective ≪ statutory, pick a stylized
     flat rate, flag as provisional. No mechanism.
  2. *Structural 2-sector demo* **[IDN, "Option B"]**: use OG-Core's multi-industry `M`/`I` machinery —
     an informal industry with `cit_rate=0`, `tau_c=0`, lower capital intensity, its own `alpha_c`
     share. Illustrative/tutorial, not revenue-anchored.
  3. *Household graded non-compliance* **[ETH, "Option A", fullest]**: `labor_/capital_income_tax_
     noncompliance_rate[t,j]` and `income_tax_filer[t,j]` grade compliance by lifetime-income group
     (a proxy for formality — informal employment share → how many bottom groups get noncompliance=1),
     with the compliant-group ETR **solved from a revenue identity** and the MTR set to the statutory
     top rate. Informality = non-*remittance*, not non-*filing* (filer stays 1). If you later add an
     informal *industry* (Option B), migrate the firm-side informality out of the CIT factor to avoid
     double-counting.
- **OG-Core structural facts (guardrails):**
  - `etr_params`/`mtrx_params`/`mtry_params` vary by **(t, age s)** only — **not** by ability type j.
    Group heterogeneity enters only through each household's income arguments.
  - `noncompliance`/`income_tax_filer` vary by **(t, j)** — not by age.
  - **`mtrx_params` = marginal rate on LABOR income; `mtry_params` = marginal rate on CAPITAL income.**
    The `x`/`y` naming is non-mnemonic — any doc/skill that says "mtrx = capital" is wrong. (ETH's
    taxes.md had this reversed; it was fixed.)
- **Known OG-Core bugs in the compliance machinery** (from the ETH informality work):
  - *SS diagnostic*: `SS.py` tiles the capital-noncompliance array from the labor rate for the
    post-solve `mtry_ss` diagnostic (doesn't affect the solution). Keep labor = capital noncompliance
    and it never bites.
  - *TPI path*: `TPI.py` applies **year-0** compliance/filer values to the whole path's revenue
    accounting, so any **time-varying** compliance reform yields inconsistent transition revenue
    (behavior responds, revenue doesn't). Steady states are fine; a formalization *reform* needs the
    upstream fix. Symptom: reform revenue tracks the baseline exactly while labor supply moves.
- **Capturing non-tax and residual-tax revenue (the "unmodeled ~4% of GDP") [PHL — net-new,
  replicate everywhere]:** OG-Core has no "other revenue" parameter, but leaving recurring non-tax
  revenue and residual taxes out understates government resources and — through the budget identity —
  forces model spending correspondingly too low. Map each stream to the instrument that prices the
  same economic margin, then tune in-model to collections:
  - *Property-type taxes* (recurrent property tax, transaction/stamp duties, local levies — the
    OECD "other taxes" residual) → the **wealth tax**: `h_wealth = 1`, `m_wealth` small-but-positive
    (`m = 0` divides 0/0 at `b = 0`; `0.001` works) makes `ETR_wealth ≈ p_wealth` flat, zero at zero
    wealth, MTR → `p_wealth`. A recurrent property tax IS a flat tax on a form of wealth, so the
    distortion lands on the correct margin (saving). PHL: `p_wealth = 0.0035` ⇒ 1.32% of GDP.
  - *Government capital income* (SOE/central-bank dividends, state gaming shares, guarantee fees,
    treasury interest income) + *unallocable income taxes* (final withholding on deposits etc.) →
    the **CIT adjustment factor** — both are government takes from capital income.
  - *Fees and charges* (user payments for services) → **`tau_c`**.
  Discipline: use only *recurring* flows — treasuries book one-offs (fund-balance transfers,
  privatization, concession fees) in non-tax revenue and often flag them themselves; exclude them.
  Two OECD-accounting traps: estate/donor taxes sit *inside* the "other taxes" residual (net them
  out or they double-count against `tau_bq`), and the income-tax *total* usually exceeds PIT + CIT —
  the difference is the unallocable withholding, real revenue that belongs on the capital side.
- **Statutory-for-effective errors bias REFORMS, not just levels [PHL]:** a CIT cut's simulated
  effect **doubled** once the adjustment factor carried true collections — the statutory rate change
  maps to a larger effective-rate change on a properly-scaled base. A calibration that over- or
  under-states an instrument's effective rate mis-sizes every reform running through it.
- **Watch for doc/code drift:** e.g. OG-IDN's `taxes.md` rates are stale vs. its shipped JSON.

## Fiscal consistency — using fiscal data to dial in the calibration

**The single most destabilizing calibration error is a government budget that does not balance at the
debt target.** The spending ratios (`alpha_G`, `alpha_T`), the revenue the tax system actually
raises, and `debt_ratio_ss` are three independently-set knobs that MUST satisfy one identity, or the
model's transition blows up. **[net-new: ZAF, proven by TPI sims]**

- **The identity.** For debt to hold at `debt_ratio_ss` in the steady state, the government must run a
  primary balance `pb* = (r_gov − g)/(1 + g) · debt_ratio_ss`, where `g = e^{g_y}(1 + g_n_ss) − 1`
  (the model's real, detrended growth) and `r_gov` is the SS real sovereign rate. So **primary
  spending must equal revenue − pb\*** — and primary spending includes public investment:
  `alpha_G + alpha_T + alpha_I ≈ Σ(revenue)/Y − pb*` (forgetting `alpha_I ≈ 0.05` mis-sets `alpha_G`
  by 5pp of GDP). Set the spending side to this, don't inherit it. With `r_gov < g` (common for EMs
  after an honest `r_gov` re-anchor), `pb*` is *negative* — the country stabilizes debt while running
  primary deficits, which usually matches its actual fiscal history. **Frame the residual honestly:**
  after capturing all recurring revenue, the remaining gap between model `G/Y` and observed
  government consumption should be ≈ (actual primary balance − pb*) — the country's genuine
  consolidation distance — plus measurement differences; name it in the docs as what the stable-debt
  SS deliberately embeds. (PHL: actual pb −2.8% vs pb* −0.7% ⇒ ~2pp embedded consolidation.) **[ZAF;
  identity-with-`alpha_I` and the consolidation-gap framing: PHL]**
- **Why it bites the transition, not the SS.** OG-Core's SS closure silently forces spending to the
  consistent level to hit the debt target, so the **steady state always solves and looks fine**. But
  the *transition* holds `alpha_G + alpha_T` at their input values for the first `tG1` periods before
  the closure adjusts — so if the input spending exceeds the consistent level, debt balloons over the
  transition before the closure violently corrects it. **With a debt-elastic premium on, that
  overshoot feeds the convex premium and the TPI runs away** (debt → ∞). Symptom: SS solves, baseline
  transition diverges or overshoots wildly. Damping and better solvers (even Anderson) do NOT fix it —
  it is a genuine fiscal runaway, not a convergence artifact.
- **Over-collecting taxes MASK the inconsistency — audit revenue by instrument.** A flat/placeholder
  tax rate set too high, or a spurious leftover tax parameter, inflates revenue and accidentally
  balances an over-set spending side; the model then looks stable until you fix the tax. Two real ZAF
  examples that hid a ~3%-of-GDP spending>revenue gap: a **flat PIT collecting ~16% of GDP** when the
  country's actual PIT is ~10% (a flat rate applied to everyone over-collects vs a progressive
  schedule), and a **spurious `tau_bq = 0.2`** (20% bequest tax) collecting 3.9% of GDP when the
  country has negligible estate duty *and the docs said bequest tax was zero* (doc/JSON drift). Check
  every revenue line against the country's actual collections **by instrument** (PIT, CIT, VAT +
  fuel/excise/customs — `tau_c` should capture ALL consumption/indirect taxes, not VAT alone —
  payroll, bequest, wealth), and grep the JSON for nonzero taxes the docs claim are off.
- **Progressive taxes expose what flat taxes hide.** A flat rate raises revenue proportionally to
  income and is robust along the transition; a progressive schedule's revenue is far more sensitive,
  so a spending>revenue gap a flat tax papered over will destabilize the transition once you switch to
  a progressive (GS/HSV) form. Don't blame the progressive form — check the fiscal balance first.
- **Reconcile against the country's OWN fiscal plan, and know what the SS represents.** Pull the
  primary-balance path and debt trajectory from the IMF Article IV / DSA and the national budget. If
  the country actually runs `pb*` (stable/declining debt), the model's SS matches current policy. If
  the country runs a deficit / rising debt (common), the model's stable-debt SS is the country's
  **targeted, post-consolidation** state — set spending to the consistent (lower) level and document
  it as such, rather than matching today's higher actual spending. Also confirm the debt is
  local-currency and rollable (usually low default risk) so you know the stable-debt SS is a modeling
  device, not a solvency claim.
- **A hot interest-growth differential forces spending too low — check `r_gov − g` against data.**
  If the model's real `(r_gov − g)` exceeds the country's actual, `pb*` is inflated and the consistent
  spending drops below the country's real spending. Diagnose both legs: `r_gov` (the LMWW wedge shift
  `μ_d` is a cross-country EM average — check it against the country's *actual* real effective
  borrowing rate = nominal debt-service/gross-debt minus inflation) and `g` (`g_y` set to a stagnant
  realized window understates a country whose debt path assumes medium-term potential growth — the
  SS is a long-run state, so a forward-looking `g_y` can be the honest choice). Bringing `r_gov − g`
  in line with the country lets spending sit at the realistic level. **[net-new: ZAF]**

## Multi-industry (M>1) — the SAM method

Build it as its own builder-regenerated file (packaging choices: mental model item 3): a
`create_multisector_calibration.py` that writes the static JSON, **one** example script
(`run_og_<xxx>_multiple_industry.py`), and shared constants (`TOTAL_CAPITAL_SHARE`,
`PUBLIC_CAPITAL_SHARE`, `CAPITAL_OUTPUT_RATIO`) in one `constants.py` so the builder and the live
Calibration can't drift.

**Finding the SAM — the sourcing hierarchy applies here too; search, don't assume one exists or
doesn't:**
- Search order: (1) the **national statistics office / central bank** — some publish an official SAM,
  and many more publish **supply-and-use tables (SUTs) / IO tables**, which are enough: the make/use
  algebra below runs on them directly (BRA: IBGE SUTs via the Alves-Passoni–Freitas annual IO
  series). (2) **Research institutes that build SAMs with the national authorities** — **UNU-WIDER**
  (country SAM program; ZAF's 2019 SASAM, distributed with a technical note) and **IFPRI** (the
  *Nexus* country-SAM program on the IFPRI Dataverse — standardized ~42-activity SAMs with
  labour-by-education/land/capital factor rows and 10 household groups; PHL's 2018 SAM) are the
  family's two workhorses, free and documented, covering many developing countries. (3) **Global harmonized/modeled databases** only as a last resort, marked
  lower-confidence: GTAP (licensed — one-time tiered fee for the current version, older versions
  free; has factor detail, being a CGE database), EORA (190-country MRIO; free for academic use,
  licensed otherwise), OECD ICIO (free; built from national SUTs but harmonized/balanced). Their
  estimation/balancing steps go beyond the national accounts, and most lack the SAM's full
  household/factor account detail — which is why they rank below a national SUT or an institute SAM.
- **What qualifies:** separate factor rows (labour — ideally disaggregated — and a capital/operating-
  surplus row), household expenditure columns, activity (and possibly commodity) accounts, an
  imports/rest-of-world account, and production-tax rows. Note whether the make is **diagonal or
  rectangular** — it decides the `io_matrix` algebra below. **Match the vintage to the rest of the
  calibration**: the employment survey year must equal the SAM year (ZAF: 2019 SASAM ↔ QLFS 2019),
  and the SAM must reproduce the same-year national accounts (structural validation, below).
- **Delivery: never read the publisher's URL at runtime** — publisher links move and break. Either
  mirror the file in the family's `EAPD-DRB/SAM-files` GitHub repo and read the raw URL (ZAF), or
  ship a compact extract in the package's `data/` (PHL, BRA). Either way record publisher, technical
  note, and year in the reader's docstring and the docs.

**Assert the concordances partition the SAM before anything else:** every activity in exactly one
`PROD_DICT` industry and every commodity in exactly one `CONS_DICT` good — a one-line set-equality
check. ZAF shipped two silently-wrong commodity codes (`colig` for `coilg`, `ccmemb` for `cmemb`)
that just dropped those commodities from every aggregation; the assert catches the whole error class.
**[net-new: ZAF]**

**Defining the industries (`PROD_DICT`) — grouping rules that prevent degenerate capital shares:**
- **Manufacturing / the capital-goods producer goes LAST** (it must be the numeraire — see structural
  facts below).
- **Never let real estate / dwellings stand alone as its own industry [PHL, BRA].** Its measured
  capital share is dominated by *imputed owner-occupier dwelling rent* — booked as operating surplus
  (capital income) but not corporate profit — which pushes its `gamma_m` toward ~1 (degenerate in the
  CES production function) and dilutes its effective CIT (imputed rent isn't taxable profit but sits in
  the denominator). Fold it into a broader **FIRE / finance–business-services** aggregate, as OG-PHL
  and OG-BRA both do. More generally, merge any activity whose surplus is dominated by imputed or
  resource rent (dwellings; watch mining/extractives) rather than modeling it alone — healthy
  capital-intensive sectors (mining, utilities ~0.78 in PHL) solve fine; it's the imputed-rent-driven
  ~0.9+ shares that break things.
- OG-Core has only **two private factors**, so **land/resource rent is folded into capital income** in
  `gamma_m` — a second reason raw SAM capital shares come out biased high (needing the VA-weighted
  rescale) and why rent-dominated activities need grouping.

**The five SAM-derived inputs** (`input_output.py`; OG-PHL is the reference, OG-BRA the most advanced):
0. **`alpha_c`** — household expenditure shares over the I consumption goods, from the SAM's
   **household columns** (purchaser prices — the budget households actually allocate), summing to 1.
   Not the legacy `total − row` shortcut (that's total commodity demand, not household spending).
   Keep the legacy naive `get_io_matrix` in place for the live `Calibration(update_from_api=True)`
   path and its unit tests — the builder uses the value-added version below; both PHL and ZAF follow
   this split.
1. **`gamma_m`** — `(capital+land)/(labor+capital+land)` per industry from SAM factor rows, then
   **rescaled** so the VA-weighted mean equals an independent economy-wide capital share (keeps the
   cross-industry pattern, fixes the level). BRA adds a per-industry mixed-income (Gollin) split first.
2. **`io_matrix`** — the **value-added** version: trace household consumption of each good back through
   the domestic supply chain to value added by industry, weighted by household consumption netted of
   imports, rows renormalized to 1. **Not** the naive direct-intermediate-cell version (a legacy
   baseline that isn't an accounting identity — IDN/ETH still ship only that legacy version). The
   correction is large: household energy spending maps to ~45% electricity in ZAF (~74% in PHL), vs. the
   manufacturing-heavy split a naive direct-use matrix implies. **Match the algebra to the SAM's make
   structure** — this is the error-prone piece: PHL's SAM has a *diagonal* make (one activity per
   commodity), which collapses to `A_d = σ·use/output`, Leontief `(I−A_d)^-1`; but a SAM that separates
   activities from commodities with a **rectangular make** (ZAF's SASAM: 61 activities × 108
   commodities, median commodity produced by >1 activity) needs the full **industry-technology make/use
   algebra** — market-share matrix `D` (`V/g`, allocates each commodity's domestic output to producing
   activities), use coefficients `B` (`U/q`), industry-by-industry Leontief `(I − D·B)^-1`, then VA per
   unit output `v = VA/q`; VA-by-activity `= v·(L @ (D @ f))` for commodity final demand `f`. The
   diagonal shortcut is *wrong* on a rectangular make. Derive `D`/`B`/Leontief from the SAM yourself
   when no pre-computed IO table ships (ZAF), or read them if it does (BRA). Sanity-check with SAM
   balance (`gross output = intermediate + VA + production tax`, machine-precision) and Leontief
   validity (spectral radius of `D·B` < 1) before trusting the result — and watch for a **"total"
   row/column** in the SAM (a 2× inflation tell) that must be excluded.
3. **`L_m` employment** — measured **independently of the SAM** (labor force survey by industry) so
   `Z_m` doesn't collapse into a mechanical function of factor shares. When the survey's industry
   aggregation is coarser than `PROD_DICT` (e.g. QLFS lumps electricity+gas+water into "utilities"),
   split the aggregate by the **SAM's labour-compensation shares** of the sub-activities, not an
   arbitrary or output-based split — a labour-intensive sub-industry (waste/sanitation) employs more per
   rand of output than a capital-intensive one (power generation). A too-low headcount in a small
   sub-industry produces a wild TFP outlier (ZAF Water&Waste `Z` fell 5.3→3.5 once split by labour
   compensation instead of a guessed 77/23).
4. **`Z_m` sector TFP** — Solow residual `Y_m/(K_m^γm · Kg^γg · L_m^(1−γm−γg))`, normalized so the
   **numeraire (last) industry = 1**. `K_m` allocates a national stock (PWT capital-output ratio ×
   total VA) across industries by capital-income share; the ratio's *level* is a weak lever (with the
   numeraire normalization it enters relative Z only through the γ dispersion) — take it from the PWT
   and move on. Reject establishment-survey capital (omits informal capital, inverts the ranking).

**OG-Core structural facts:**
- The **last industry (index M−1) is the numeraire and the only non-consumption producer** — all
  investment, government, net-outflow, remittance, and aid demand loads on it, so its nominal output
  share is inflated and is *never* comparable to a value-added share. **Put the capital-goods /
  manufacturing industry LAST** in `PROD_DICT`.
- **One economy-wide wage; households don't choose a sector** (`L_m` is firm-side labor demand). A
  formal/informal wage gap or sector-choice margin is *not* representable without extending OG-Core.
- `cit_rate`/`tau_c`/`delta_tau`/`inv_tax_credit` **can** vary by industry/good; wage and household
  labor supply cannot.
- The composite-consumption price is **unnormalized**, carrying a units constant `k =
  prod_i(alpha_c_i^−alpha_c_i)` (=1 when I=1) — behaviorally relevant, not cosmetic.

**Single ↔ multi compatibility** (so the two representations agree):
- **Copy economy-wide values verbatim** (demographics, preferences, fiscal ratios, open-economy dials,
  `g_y`, statutory rates) — any difference is a bug.
- `gamma_m`: keep the SAM's dispersion, **impose the single model's level** (VA-weighted mean).
- `Z`: relative TFPs from the Solow residual with numeraire = 1. **Two distinct uses of the Z *level*
  (a common Hicks-neutral rescale) — don't conflate them:** (a) to close *rate/ratio* gaps (r, K_f/K)
  it is a weak, sometimes wrong-signed lever — don't (PHL: an 11.7% Z rise moved r the *wrong* way);
  (b) to align the *income level* (`factor`) it is the correct, clean lever — r, r_gov and K/Y are
  invariant to it, only the income level moves. The numeraire=1 convention pins relative TFPs but leaves
  the level free, and whether it *happens* to land `factor` on the single's is luck (PHL: −0.02%, no
  rescale; ZAF: −23%, needed one). So: if `factor` is still off after the chi conversion, rescale the
  **whole Z vector by a common constant** (a quick log-log root-find on solved-SS `factor` converges in
  2–3 solves; β≈1.8 for ZAF) so the multi's factor matches the single's. `factor` *must* agree — it
  scales the incomes at which the (progressive) tax functions are evaluated, so a 23% factor gap
  mis-collects PIT.
- **The `chi_n`/`chi_b` units conversion is THE alignment lever:** scale both by `k^(σ−1)`, derived
  (not fitted) from FOC-invariance under the composite-consumption units change. In PHL this closed
  44–80% of the r / K_f/K / B/Y / K/Y gaps.
- **Solver seeds are the single-industry model's — never separately tune seeds for the multi.** Lean
  overlay: don't copy them in (inherit from the base at load). Self-sufficient file: the builder's
  merge copies them verbatim and regeneration keeps them synced. Either way the multi cold-starts from
  the single's seeds — which works because the multi's flat anchor *is* the shared aggregate economy.
- **Final acceptance: run the SAME reform through both models** and compare the percent-change tables —
  same signs, similar magnitudes (ZAF: CIT 27→30% through M=1 and M=8; all six aggregates agreed).
- **Comparison dashboard:** must-match (D/Y, tax rates); close (K/Y, `factor` — a big factor gap means
  a level misalignment upstream); ballpark with a written reason (r, K_f/K, B/Y); never compare raw
  (Y/w/C levels, raw C/Y in multi — use `p_tilde·C/Y`, the numeraire's nominal share).

**The continuation solve** (a fallback for when the calibrated multi-industry SS won't solve cold —
OG-Core seeds every industry price at 1). **Try the direct solve first:** ZAF's M=8 converged cold from
the shared base-JSON seeds in ~130s (the flat anchor ≈ the single economy, so the single's seeds are
close), so reach for continuation only if the direct solve fails:
1. Solve a **flat anchor**: all `gamma = economy-wide mean`, `Z = 1`.
2. Walk `t: 0→1`, morphing `gamma(t)` and `Z(t)` **together** to the calibrated values, each step a
   warm-started reform off the previous; grow the step on success, halve on failure.
3. Use **heavier TPI damping, `TPI_NU ≈ 0.2`** (the default 0.4 oscillates; 0.3 is marginal). ogcore
   ≥0.16.4 adds opt-in Anderson acceleration (`TPI_outer_method="anderson"`) as a further lever for
   stiff multi-industry TPI — but remember neither damping nor Anderson fixes a *fiscal* runaway
   (see Fiscal consistency); solver knobs treat oscillation, not an unbalanced budget.
4. Reuse the continuation's converged SS for the baseline TPI (hand-place the pickle) — only the
   reform re-solves its own SS.

**Maturity honesty:** OG-PHL is the reference (the complete version, with the chi conversion, lives on
PR EAPD-DRB/OG-PHL#63's branch, not `main`); OG-BRA is the most advanced port; **OG-ZAF has now
executed the full SAM-Solow method** (make/use-Leontief value-added `io_matrix`, VA-mean-rescaled
`gamma`, Solow-residual `Z` with QLFS employment, the chi conversion, and a factor-aligning Z-level
rescale — a self-sufficient JSON regenerated by `create_multisector_calibration.py`; PR
EAPD-DRB/OG-ZAF#142). OG-IDN and OG-ETH have **not** — their shipped multisector JSONs are partial or
placeholder (OG-IDN even ships the flat *anchor* gamma/Z as if calibrated). Don't treat a sibling's
multisector JSON as a worked example without checking `input_output.py` has the real
`get_gamma`/`get_Z`/value-added `get_io_matrix` functions.

## Step zero: write the equations down before you touch a parameter

**Before tuning anything, produce a moment x lever table and commit it.** Not from
convention, not from this skill's parameter tables — from the equations OG-Core
actually evaluates, read out of `firm.py`, `aggregates.py`, `household.py`,
`fiscal.py` and `tax.py`. It takes under an hour and it is the single highest-value
hour in a calibration.

For each target moment, write three things:

1. **The closed form**, with every symbol in it. Reproduce the solved value from your
   own formula to 4 decimals before trusting it — a mismatch means you read the wrong
   equation, and finding that out now costs minutes.
2. **Every parameter appearing in it**, each marked `sourced` / `tuned-to-<moment>` /
   `DEFAULT-unexamined`.
3. **Which other moments share those levers.**

Worked example — `K/Y`, where convention names exactly one instrument (`beta`):

```
K/Y = (1 - tau_b)·gamma / (r + delta - tau_b·delta_tau - inv_tax_credit·delta)
      [firm.get_r, Cobb-Douglas]

  gamma            sourced (PWT labour share)
  delta            sourced (CFC/K)
  tau_b            = cit_rate x c_corp_share_of_assets x adjustment_factor
                     c_corp_share_of_assets = 0.55 is a US DEFAULT, and note it is
                     NOT separately identified from adjustment_factor -- only the
                     product is
  delta_tau        DEFAULT 0.027 (US tax depreciation)
  inv_tax_credit   DEFAULT 0.0
  r                NOT a parameter -- household Euler pins the PORTFOLIO return r_p,
                     and r solves r_p = weighted avg of r (on K) and r_gov (on D).
                     So beta, sigma, g_y, debt_ratio_ss, r_gov_scale/shift,
                     zeta_K and world_int_rate are ALL levers on K/Y.

  shares levers with: C/Y (via I), I/Y, K_f/K, r
```

That table has eleven levers. The conventional answer has one. OG-JPN tuned the one,
watched it run out of road at `beta = 0.984`, wrote "acceptable band", and shipped —
while `zeta_K` sat at a placeholder that closed over half the gap when set from data.

**The table is also the tuning ORDER.** Sourced levers first, then the tuned dials,
then re-check anything sharing a lever with what you moved.

## Finding every lever on a moment — do this BEFORE you tune

The failure this section exists to prevent, in full: OG-JPN's `K/Y` came in at 3.50
against a PWT 3.70. `beta` is the conventional instrument, it needed 0.984, and at
0.984 the steady state stopped solving. That was written up as an acceptable miss and
a "family trait". It was neither. `zeta_K` — capital-account openness, sitting at a
placeholder 0.10 that the repo's own comment labelled `NEEDS TUNING ... pending the
IIP anchor` — closed **79% of the `K/Y` gap and 85% of a separate consumption gap**
when set to the value the IIP data had been specifying all along. Fourteen tuning
rounds ran without touching it.

Four rules, all mechanical. None of them require noticing anything.

**1. Write the model's own closed form for the moment, then list its arguments.**
Not the conventional pairing — the equation OG-Core actually evaluates. For `K/Y`,
`firm.get_r` gives `r = (1-tau_b)·p_m·MPK - delta + tau_b·delta_tau + tau_inv·delta`,
so under Cobb-Douglas:

```
K/Y = (1 - tau_b)·gamma / (r + delta - tau_b·delta_tau - inv_tax_credit·delta)
```

That names **six** levers plus everything moving `r`, where convention names one
(`beta`). Reproduce the solved value from the closed form before trusting it — if it
does not match to 4 decimals you have the wrong equation, and finding that out costs
minutes rather than a shipped calibration. Then extend to `r`: the household Euler
pins the **portfolio** return `r_p`, and `r` is whatever makes the capital/debt blend
equal it. So `debt_ratio_ss` and `r_gov` are levers on `K/Y` too — a bigger stock of
zero-yielding government debt forces capital to pay more, which shrinks `K`.

**2. Every parameter ends in one of three states, and "placeholder" is not one.**
Sourced · tuned-to-a-named-moment · deliberately-defaulted-with-a-written-reason.
A `NEEDS TUNING` marker is a **debt with an exit criterion**, not a note to self.
Grep for the marker as a release gate and make it a test — `test_no_unresolved_tuning_markers`.
The JPN comment even named the dataset to use; it shipped anyway, because nothing
failed when it didn't.

**3. Two moments that move together are ONE moment — check for shared levers before
diagnosing either.** Build the moment × parameter table from rule 1 and look for
overlap. JPN's consumption gap (+2.3pp) and `K/Y` gap (−0.20) were analysed
separately for an entire calibration, including a full decomposition of consumption
into investment / government / net exports. They were the same gap: too little capital
means too little investment, and `C = Y - I - I_g - G - NX` makes consumption the
residual that absorbs it. One lever closed both. **Symptom-by-symptom tuning will
always find a spurious "structural" residual** — because fixing one symptom moves the
other and you conclude the model can't do better.

**4. A lever that runs out of road is the WRONG LEVER, not proof the gap is
structural.** When the instrument needs a value that will not solve, or one outside
its plausible range, that is diagnostic information about the *instrument*. Escalate
to rule 1; do not write "acceptable band". The band language is how a calibration
launders an untuned parameter into a family trait.

**Then: sweep the defaults you did NOT source.** Perturb every unsourced parameter and
record which target moments move. Anything that moves one materially must be sourced or
explicitly declared — and the catch is that **relevance depends on the settings you have
not chosen yet.** `world_int_rate` (OG-Core default `0.04`) is invisible at `zeta_K = 0.10`
and *sets* `r` at `zeta_K = 0.78`; dropping it to 3.5% moved JPN's `K/Y` from 3.67 to 3.81
and `K_f/K` from 17% to 27%. So high openness silently transfers the determination of the
country's interest rate from its own households' preferences to an unsourced global
constant. Run the sweep **after** the parameters settle, not before. **[net-new: JPN]**

## Warm-starting the steady state — do this before you debug anything else

**If a country's steady state will not converge, suspect the cold start before you
suspect the calibration.** OG-Core seeds the household problem from *constants*:
savings at a hardcoded `0.07` for every age and income group (`SS.py`, carrying its
own `TODO: remove hardcode`), labour at 0.35, and the bequest guesses derived from
those. For a wealthy, ageing, high-saving population that is not imprecise, it is
catastrophic:

- the bequest seed lands **two orders of magnitude low** (JPN: 134× in aggregate,
  349× for the top income group, against solved savings of ~6.1 versus the seed's
  0.07);
- domestic capital `K_d = B − D_d` therefore starts **negative** — wealth near zero
  against domestically-held government debt — so `SS_fsolve` clamps it and
  substitutes `1e9` residuals, **destroying the finite-difference Jacobian** the
  default `hybr` root-finder depends on; and
- `initial_guess_factor_SS` is validated to a maximum of **500,000** while a
  low-unit currency needs far more (JPN ~7e6, IDN worse), so the correct seed
  cannot be entered as a parameter at all.

**The failure mode disguises itself.** `run_SS` does not report failure — it
silently restarts down a 39-rung ladder of rescaled seeds
(`ogcore.constants.DEV_FACTOR_LIST`), making a separate `opt.root` call per rung.
What presents as "hundreds of slow iterations" is several *failed solves stacked
end to end*. Count restarts, not iterations: a jump in the residual of 50× or more
between consecutive evaluations is a new rung starting, not progress.

**The fix.** Seed from a state that has already solved — the household matrices
`b` and `n` **and every outer unknown together**, so they are mutually consistent —
and pass `factor` directly, which bypasses the validator cap. Measured on JPN,
identical parameters, same 7-worker client:

| | evaluations | restarts | residual |
|---|---:|---:|---:|
| cold start | >175 | several | never converged |
| **warm start** | **18–22** | **none** | **5.5e-11** |

`b` and `n` are in MODEL units, so a seed stays valid across changes to the
currency scale, the demographic window and modest parameter moves. Ship the seed
with the repo (it is ~9 KB) and regenerate it after any large recalibration —
without it a fresh checkout cannot solve. Reference implementation:
`ogjpn/warm_start.py` + `examples/save_warm_start.py`.

**Warm-starting is NOT the same as retuning the seed parameters, and the difference
matters.** Setting `initial_guess_r_SS`/`TR_SS` to their solved values was tried on
JPN and made things *worse* — the family's existing "nearness ≠ solvability" rule.
The scalars are 3 of 14 unknowns; the household matrices are 560 numbers and are
what the bequest seed is computed from. Warm-start the matrices; leave the scalar
parameters alone.

**TODO — automate this.** Every country repo will hit it, and it has bitten this
family before. The seed should be produced and reused without hand-holding:
a `--save-warm-start` flag on the standard example that writes the seed on every
successful solve, and an `enable()` called by default; then a shared helper so each
repo is not re-deriving the same shim. The proper fix is upstream — ogcore should
derive its seeds from parameters it already has (`b ≈ (K/Y + D_d/Y)·Y` from the firm
FOC and the debt parameters) and accept a warm start — but the repo-side helper is
worth having regardless, because it also makes reruns cheap. **[net-new: JPN]**

## Dashboard completeness — an unscored moment cannot pull its parameter

This is the general form of the `zeta_K` failure, and it is worth more than any
individual parameter tip in this skill. `zeta_K` sat at a placeholder through
fourteen tuning rounds **because `K_f/K` was not a row on the validation dashboard.**
Nothing was wrong with the tuning loop. The loop optimised what it could see.

Three rules, all checkable mechanically:

**1. Every tuned parameter's identifying moment must be ON the dashboard.** If you
tuned a dial to a target, that target is a moment — score it. Cross-check the two
lists (`grep` the tuned dials, `grep` the dashboard rows) and require a bijection.
A dial with no scored moment will drift, silently, and nothing will fail.

**2. A dial moved to close a RESIDUAL is a free parameter, not a calibration.**
OG-JPN's `p_wealth` and `tau_bq` were nominally tuned to property-tax and
inheritance-tax revenue, but in practice were scaled to close the gap in *total*
revenue — which meant they absorbed every other line's error. Tune each dial against
its **own** moment, and let total revenue be the check that the parts add up, never
the thing you steer.

**3. Score every component of the resource constraint, not just the residual.**
`C = Y - I - I_g - G - NX`. Scoring only `C/Y` cannot tell you which term is wrong,
and it invites the symptom-by-symptom error above. Put `I/Y`, `I_g/Y`, `G/Y` and
`NX/Y` on the dashboard next to it.

**The moments most often tuned-for but never scored, and where the data lives:**

| Moment | Parameter it identifies | Source |
|---|---|---|
| `K_f/K` | `zeta_K` | IIP: inward DI equity + portfolio equity, ÷ GDP ÷ `K/Y` |
| `(I + I_g)/Y` | `delta`, `alpha_I` | national accounts GFCF — **private + public**, `I_total` alone is private |
| `G/Y` | `alpha_G` | government final consumption. Score the SOLVED value: OG-Core's SS silently forces spending to the budget-consistent level, so it will differ from your `alpha_G` input, and that difference is information |
| `NX/Y` | `zeta_K`, `zeta_D` | the **trade** balance, not the current account — see below |
| property / wealth tax / Y | `p_wealth`, `h_wealth` | revenue statistics |
| bequest tax / Y | `tau_bq` | revenue statistics |
| `w·L/Y` (solved labour share) | validates `gamma` **and** `epsilon` | PWT `labsh`. JPN solved 0.5700 against 0.571 — a genuine free check, since nothing forces it when `epsilon != 1` |
| wealth Gini / top shares | the `e` matrix, `beta` | household wealth surveys. Distinct from the INCOME Gini the tilt targets, and a much sharper test of an OG model |
| `g_n_ss` | the demographic window | the UN projection's own implied CAGR |

**Two traps when you add these rows:**

- **Check whether the SS key is an aggregate or a per-household array.** `wealth_tax`
  and `bequest_tax` come back shaped `(S, J)`. Summing them gives a number with no
  units — OG-JPN got 16.7 "of GDP" — which looks so wrong it gets discarded rather
  than debugged. Weight by `omega_SS` and `lambdas`, and sanity-check every new row
  against a plausible magnitude before believing a gap.
- **`NX` is the TRADE balance; the current account is a different object.** For a
  country with a large net international investment position most of the current
  account is primary income, not trade. Japan's CA surplus is ~3.8% of GDP against a
  goods-and-services balance near zero — so a model `NX/Y` of 0.000 is right and
  scoring it against 3.8% would be a concept error.

**`K_f` GROSS vs NET — settle this before you tune `zeta_K`, because the two
readings differ in SIGN for a net-creditor country.**

The identity is `K = K_d + K_f` with `K_d = B − D_d`, so `K_f` reads as the
**gross** foreign-owned share of the domestic capital stock — households hold
domestic capital and domestic government debt, and nothing else. On that reading
the IIP target is inward direct-investment equity (incl. reinvested earnings) +
inward portfolio equity, ÷ GDP ÷ `K/Y`. Japan end-2024: (34.5 + 334.8) / 609 / 3.70
= **+16.4%**, against the 1.5% a placeholder `zeta_K = 0.10` was producing.

But `K_f = zeta_K·(K_demand_open − B + D_d)` is **not clamped**, and the outflow
term `(r + delta)·K_f − new_borrowing_f + debt_service_f` reverses cleanly, so a
*negative* `K_f` is arithmetically fine and reads as a **net** creditor position.
Japan's net IIP is **+¥533tn, 87.5% of GDP** — on the net reading the target is
**−23.7%**, the opposite sign.

**Which to use.** The identity is the stronger argument: `K_d = B − D_d` leaves
households no foreign asset to hold, so negative `K_f` is an unclamped edge case
rather than a designed representation. Calibrate to **gross**. But say plainly
what that costs — the model then omits the country's foreign portfolio entirely:
household wealth `B` is understated by it, and the primary income it earns is
absent from the resource constraint. For Japan that is ¥1,659tn of assets and
roughly 3.8% of GDP a year of income. **This is a genuine OG-Core limitation, not
a calibration choice:** there is one `K_f`, so a two-sided external balance sheet
cannot be expressed. Check the sign of the country's NIIP, state which reading you
took, and note the omission in the audit. **[net-new: JPN]**

**Pension outlays belong in the fiscal identity.** The identity elsewhere in this
skill reads `alpha_G + alpha_T + alpha_I ≈ revenue/Y − pb*`. For any country with a
modelled pension system that is **incomplete** — pensions are a primary outlay like
any other:

```
alpha_G + alpha_T + alpha_I + agg_pension_outlays/Y  =  revenue/Y − pb*
```

Omitting them sets `alpha_G` too high by the whole pension bill's worth of error
(JPN: 0.63pp of GDP). **And the SS will not tell you** — the closure forces `G` to
the consistent level, so the steady state solves and simply reports a `G/Y` below
your `alpha_G` input. That silent gap between input and solved `G/Y` IS the
diagnostic; read it every solve. The transition has no such closure for the first
`tG1` periods, so it over-spends the full error. **[net-new: JPN]**

## Validation — the near-term fiscal path FIRST, then the joint steady state

**Priority, and it is the reverse of how most of this family works.** The steady state is a
destination decades out that nobody will live in. The **near-term fiscal path is the more
believable test**, and it should be built and scored *before* the SS dashboard is polished:

- **It is checkable against things that actually happened.** Debt, primary balance and revenue for
  the last several years are published, and the next few are projected by the IMF/OECD and by the
  country's own medium-term fiscal framework. A model that reproduces them is credible in a way
  that "our steady state resembles a stylised long run" never is.
- **It is the ONLY test that can see the debt level.** In the steady state `D/Y` *is*
  `debt_ratio_ss` — a policy anchor you chose — so scoring it there compares a choice against a
  measurement and tells you nothing. `initial_debt_ratio` is a measurement, and only the transition
  starts from it. **JPN shipped `initial_debt_ratio = 0.864` against an actual 1.148 — a 28pp-of-GDP
  error — for a full day, in a file whose own `r_gov` derivation used the correct 114.8%.** The SS
  dashboard was structurally incapable of catching it; a debt-path panel would have shown it in
  period one. **[net-new: JPN]**
- **It is where a fiscal miscalibration actually bites.** The SS closure silently forces spending to
  the consistent level, so the steady state solves and looks fine no matter what. The transition
  holds `alpha_G`/`alpha_T` at their input values for `tG1` periods and has no such protection.

So: **build the path panel with the SS dashboard, not after it.** Both are required; the path is the
one that can be falsified by next year's data.

### Transition-path validation against the fiscal program [PHL — net-new; JPN — promoted to first-rank]

Compare the **baseline TPI paths** of the fiscal variables against the country's own published
program and the international projections:

- **The comparison set** (model from `TPI_vars.pkl`, first ~10–15 years): primary balance
  (`total_tax_revenue − total_primary_government_outlays`)/Y vs the treasury's actual primary
  balance + the medium-term program's (deficit path less programmed interest); `D/Y` vs actual debt
  ratios + the program's trajectory/targets; total revenue/Y vs the program's revenue effort **with
  a stated concept bridge** (model revenue is general-government accrual + captured non-tax; NG cash
  programs need a wedge — derive it from one overlap year of OECD-vs-treasury data and hold it
  constant); `I_g/Y` vs the program's infrastructure path. Sources: the MTFF-class medium-term
  fiscal framework (deficit/revenue/disbursement/infra paths), the budget document (interest
  projections, to convert deficit→primary), treasury cash-operations reports (actuals).
- **The alpha_G glide — put the transition on the government's consolidation schedule.** A flat
  identity-value `alpha_G` makes the model consolidate *immediately* (pb jumps to pb* in year one,
  typically years ahead of the actual plan), which pays debt far below target early (PHL: down to
  ~48% vs a 58–61% program band) before the closure brings it back. Instead set `alpha_G` as a
  declining path: `alpha_G(t) = SS_revenue_share − pb_program(t) − alpha_T − alpha_I(t)` for each
  program year, **capped at the identity-consistent value from the year the program's primary
  balance crosses the model's pb*** (don't chase extended-projection years tighter than pb* — that
  re-introduces the undershoot). The SS is untouched (the closure ignores `alpha_G`); only the
  transition's stance changes. Bonus validation: if the program's own consolidation converges to
  pb* near the end of the program window, the steady state is literally where the government's plan
  is headed — say so in the docs.
- **A violent early-transition spike is a diagnosis, not a feature.** A one-to-two year consumption
  / consumption-tax-revenue pulse at the start of the baseline is the fingerprint of the imposed
  initial-wealth condition (see the `initial_wealth_ratio` row in the macro table) — check the
  B_ss/B0 scale factor and fix it with the parameter BEFORE labeling anything benign. (An earlier
  version of this skill advised documenting the spike as "transition dynamics"; that normalized a
  fixable artifact.) The dynamics that legitimately remain after the fix: convergence from a
  non-stationary initial age distribution and capital stock, and — under a fiscal glide — the
  early-transition growth rate exceeding its long-run value, which erodes the debt ratio before the
  arithmetic tightens. Never tune fiscal parameters against whatever residual is left.
- **Deliverable:** a small multi-panel figure (debt ratio, primary balance, revenue, public
  investment; model line vs actual dots vs program markers) committed to the docs images with a
  caption naming every source, referenced from the macro chapter's validation section — and axis
  limits that show the model's full path (clipping the divergence you're testing for defeats the
  exercise).

- **Build a steady-state validation dashboard [emerging: IDN, ETH — adopt it].** A table in `macro.md`
  comparing the solved SS to country data targets, each with a source column. Recurring moments: `D/Y`,
  `D_f/D`, `K_f/K`, `K_f/Y`, `C/Y`, `(I+I_g)/Y`, `K/Y`, `I_g/Y`, `TR/Y`, `NX/Y`, `RM/Y`, `r`, PIT/Y,
  CIT/Y, `T/Y`. The governing sentence: *"most parameters are only weakly identified on their own, so
  the real test is whether the steady state they jointly produce resembles the economy."*
- **Revenue by instrument:** don't just check total tax/GDP — check PIT, CIT, VAT, payroll each against
  collections. Offsetting errors can make the total look right while the composition is wrong.
- **Source the data side by actively searching for the most authoritative source that exists — never
  fill the dashboard from memory, and never treat any source list (including this one) as closed.**
  A wrong data anchor silently fails an otherwise-correct calibration, so treat the data column as
  carefully as the model column. For each moment, search in descending order of authority and stop at
  the highest rung that has the number:
  1. **The official national institution that *owns* the number** — the agency that administers it:
     revenue service for collections, treasury/finance ministry (budget review, fiscal framework,
     debt bulletin) for spending/debt/debt-service, statistics office for GDP-by-industry / HFCE /
     the labour force survey, central bank (quarterly bulletin, IIP) for external and monetary data.
     Institution *names* differ by country — search by **role** ("who administers this number
     here?"), and expect to find ministries, debt-management offices, planning commissions, or
     social-security agencies you didn't know existed. Their publications outrank everything else.
  2. **Official international compilations of national data** — IMF (Article IV statistical
     appendix, GFS, WEO), World Bank, UN, ILO, PWT — often the same national numbers, re-published
     with a lag and on standardized definitions (useful for cross-checks, weaker on vintage). For
     the whole revenue side, the **OECD Revenue Statistics country note** (Asia-Pacific / LAC /
     Africa editions, free 4-page PDFs) is the single best table in the family's experience **[PHL]**:
     every instrument as % of GDP on one accrual basis and one GDP vintage — PIT, CIT, SSC, VAT,
     excises, customs, and an "other taxes" residual. Pair it with the treasury's cash-operations
     report for non-tax revenue, interest payments, and the actual primary balance.
  3. **Regional development banks and bodies** — AfDB/ADB/IADB/EBRD country diagnostics, regional
     statistical commissions — frequently carry country detail (sector data, informality, fiscal
     risk) that neither the national site nor the IMF publishes cleanly.
  Typical role→moment map to start from: tax ratios ← revenue service *tax statistics* + budget
  review; debt / foreign-share / effective `r_gov` (= debt-service ÷ gross debt, deflated) ← budget
  review / debt office; sector value-added shares ← GDP-by-industry release; household consumption
  shares ← HFCE / expenditure survey / CPI weights; employment by industry ← labour force survey;
  `K/Y` ← PWT. Adversarially re-check the load-bearing numbers against a second, independent source.
  When the search genuinely comes up empty at every rung, use the best lower-rung number, note the
  vintage, and mark the moment lower-confidence rather than dropping it from the dashboard.
- **Mind the GDP vintage — the silent ratio trap.** When the statistics office *rebases* GDP, every
  `x/GDP` ratio moves without anything real changing (South Africa's 2021 rebasing shifted tax-to-GDP
  ~2.6 pp: 23.7% on the rebased base vs 26.3% on the old base, *same year*). Compare a model ratio to a
  data ratio on **one consistent GDP vintage**, and say which — a calibration tuned to an old-vintage
  ratio will look ~2–3 pp off against current data for no real reason.
- **Read the model side from the solved SS object** (`safe_read_pickle` on `SS_vars.pkl`), don't
  eyeball it: fiscal ratios are revenue lines over `Y` — PIT `iit_revenue/Y`, CIT
  `business_tax_revenue/Y`, indirect `cons_tax_revenue/Y`, total `total_tax_revenue/Y`; `D/Y`, `D_f/D`,
  `K/Y` from the aggregates over `Y`; `r`, `r_gov`, `factor` directly; consumption share as
  `p_tilde·C/Y` (never raw `C/Y` when `I>1`).
- **Structural validation (multi-industry) — check the SAM reproduces the national accounts before
  trusting it.** The SAM's value-added shares by broad sector should track the statistics office's
  GDP-by-industry (a 2019 SA SAM matched Stats SA to ~0.5 pp on primary/secondary/tertiary); employment
  shares should match the LFS (they are the source); `alpha_c` should match HFCE's goods/services
  split. A SAM that doesn't reproduce the national accounts' sector structure is the wrong vintage or
  mis-aggregated — fix that before reading anything else off the multi-industry SS.
- **Note derived quantities honestly:** e.g. "net exports" is a balance-of-payments *residual* of the
  resource constraint (OG-Core has no trade sector), not a modeled export/import.
- **Consumption is a residual — diagnose it, never tune to it [net-new: JPN].** There is no
  consumption parameter: `C = Y − I − I_g − G − NX`, so a consumption gap is *identically* the sum of
  the other three. Decompose it; each piece has its own cause. Related trap: **`I_total` in the SS
  output is PRIVATE investment**, while national-accounts GFCF is private *plus* public — compare
  `I_total + I_g`, or the gap is overstated by all of public investment.
- **`g_n` is a path; the steady state uses its terminal value [net-new: JPN].** For a country
  mid-demographic-transition those are very different numbers (JPN: −0.33% today, −0.46% terminal), so
  a steady-state moment that depends on `g` — investment above all — will look wrong against *today's*
  data even when the calibration is right. The honest comparison for "does this look like the country
  now" is the early transition. Say which one a dashboard row is scoring.
- **Pair the debt concept with the interest concept [net-new: JPN].** Where a government holds large
  financial assets, net and gross debt differ enormously: net debt must be paired with *net* interest,
  gross with the effective rate on *gross*. The test is whether `r_gov × D` reproduces the actual
  interest bill. Either pairing is defensible; mixing them is not.
- **Audit each instrument's BASE, not just its yield [net-new: JPN].** A right total can sit on a wrong
  rate applied to a wrong base, and only the base test separates them. A rate tuned in-model to a
  revenue target on a base the model gets wrong gives the right *level* and the wrong *reform
  response* — so **size reforms by the revenue they must raise, not by the rate change**, which cancels
  the base error because the same base appears in numerator and denominator.
- **Know the family traits before "fixing" them:** the model's endogenous `K/Y` runs high against the
  PWT across the whole family (ZAF 4.5 vs 3.7; PHL 4.3) — a structural feature of the saving/return
  block, not a country-calibration error. Report it with a written reason in the dashboard's ballpark
  tier; don't distort a country parameter to chase it.
- **Fast value-pinning test [emerging: ETH — adopt it].** A `test_default_parameters.py` that loads the
  shipped JSON and pins specific calibrated values with inline source citations, explicitly *not*
  asserting anything that needs a solve. Separate this from the slow example smoke test.
- **Prevent doc/JSON drift with `{glue:text}` [emerging: ETH — adopt it].** A hidden code-cell in the
  docs loads the packaged JSON and `glue()`s the numbers, so prose can never drift from the shipped
  values.
- **The in-model tuning loop is cheap — use real solves, not algebra [PHL].** A warm-guess SS solve
  is ~15s (single worker, no dask), so the workflow *solve → read revenue dashboard → adjust dials →
  re-solve* converges in 3–5 iterations for half a dozen simultaneous dials (GS φ2, `tau_c`, CIT
  adjustment, `p_wealth`, `r_gov_shift`, `zeta_K`). Keep a driver script that loads the packaged
  JSON + an overrides dict, solves SS-only, and prints model-vs-target by instrument. Always finish
  with a **standalone solve of the packaged JSON itself** (no overrides) — it catches schema errors
  and guess problems the overrides path hides.
- **Run engineering: call the model the way the example scripts do — everything through the client.**
  Every sibling `run_og_<country>.py` does `num_workers = min(cpu_count(), 7)`, one
  `Client(n_workers=num_workers, threads_per_worker=1)`, and **one**
  `runner(p, time_path=True, client=client)` per scenario. The steady state solves through the client
  too. That is slower on the SS — measured ~38s per GE evaluation against ~6s serial — and it is the
  accepted price of invoking the model exactly as the family does rather than through a hand-rolled
  driver that can differ subtly from the shipped path. **`min(cpu_count(), 7)` is not a guess:** both
  `SS.py` and `TPI.py` parallelise with `client.submit` inside `for j in range(p.J)` and `J = 7`, so an
  eighth worker idles — seven IS maximum parallelism, on any machine. **The trap to avoid**, because it
  looks like an optimisation and is neither pattern: `runner` **always re-solves the steady state**, so
  stacking `runner(time_path=False)` then `runner(time_path=True, client=client)` solves it twice, the
  second time the slow way round. `TPI_outer_method = "anderson"` belongs in the packaged parameters,
  not the script — and note it is **TPI-only**: it appears zero times in `SS.py`, so it does nothing for
  a steady-state problem. **[net-new: JPN, superseding the earlier SS-serial advice]**


- **Triage an `RC_error` by WHERE IN TIME it happens [net-new: JPN].** ogcore pickles TPI output
  *before* it raises, so read `TPI_vars.pkl["resource_constraint_error"]` even from a failed run. The
  location is the diagnosis: **smooth and decaying over the first several periods** → initial
  condition, i.e. `initial_wealth_ratio` (the PHL windfall); **isolated single-period spikes** → a
  discontinuity in a time-varying input at exactly that period (check `rho`, `imm_rates`, `omega`,
  `retire`, `etr_params` for a jump — this is how the demographic-window and `fixper` problems
  surfaced); **growing along the path with debt rising** → the fiscal runaway. Check the outer-loop
  distance series first: if it fell monotonically and debt is flat, the solver is fine and the problem
  is an input.
- **The tuning loop converges in 3–5 rounds only once the SOURCED parameters are settled
  [net-new: JPN].** Any change to a sourced parameter invalidates every tuned dial below it, because
  they were fitted against the old base. Work in this order and expect one full retune per upstream
  correction: (1) sourced structurals — `gamma`, `delta`, `g_y`, the demographic window, spending
  shares; (2) tuned tax dials against the revenue targets; (3) `beta` against `K/Y`; (4) retune (2) if
  (3) moved the bases. JPN took **fourteen** rounds because `gamma`, `delta`, `g_y`, `alpha_T` and the
  window were each corrected *after* the tax dials were tuned. Audit the whole parameter surface
  BEFORE starting the loop, not one parameter at a time.
- **Verify BOTH tails of every path, and read the figure you just made [PHL — a caught error].** A
  min-only check on the debt path ("trough = 60.0, stays on target") passed while the path actually
  climbed to 74% — the check tested only the direction the PREVIOUS failure pointed. For every path
  claim report min AND max with their years, and eyeball the plotted line before writing the
  sentence about it.
- **Running a country model against an unreleased ogcore branch [PHL].** `uv run --with-editable
  <ogcore-checkout>` can silently resolve ogcore from the uv CACHE, and probing with `python -c`
  from the checkout root masks it via cwd shadowing. The working pattern: run from the ogcore
  checkout's env with the country repo overlaid (`cd OG-Core && uv run --with-editable ../OG-XXX
  python driver.py`), pin `sys.path.insert(0, <ogcore-checkout>)` in the driver, and `assert
  <checkout> in ogcore.__file__` before anything else — the assert has caught real contamination.
  Keep the packaged JSON loadable on RELEASED ogcore too: tests that build a `Specifications`
  strip not-yet-released parameters when absent (`hasattr` guard), so the suite stays green on
  both.
- **Initial-guess fragility: nearness ≠ solvability [PHL].** Guesses retuned to the *exact* solved
  values (factor to 5 digits) sent the solver through a `K_d < 0` region and failed the SS, while
  older, farther guesses converged cleanly. Choose packaged guesses by solve-path robustness — keep
  the set that works, don't chase proximity. Relatedly, transient `"K_d has negative elements"`
  warnings during iteration are benign **iff** the identities hold in the saved pickle
  (`K = K_d + K_f`, `K_d = B − D_d`) — check the pickle, not the console.
- **Derived parameters regenerate together [PHL].** Anything computed *from* demographics —
  the model-consistent `g_RM` path (from `g_n`), the `eta_RM` matrix (from `omega_SS`) — belongs in
  the demographics-regeneration tool so a demographics rebuild can't leave it stale, with a test
  asserting packaged value == constructor(packaged inputs).

## House rules (lift verbatim into any port)

- **uv only, run as a user would.** Don't hand-pick a Python; let uv resolve Python + ogcore.
- **Never commit a `uv.lock` change** from calibration work; keep it out of the PR diff.
- **Non-destructive:** the single-industry default must keep working; ship multi-industry as its own
  builder-regenerated file (lean overlay or self-sufficient — see the packaging choices in the mental
  model), never by editing the single-industry JSON.
- **Document every calibrated value with a source** — even stylized placeholders (family norm; a few
  repos' tax docs still lack inline citations — add them when you touch those docs).
- **Ask before push, ask before PR — never in the same step.** PR style: narrative, plain language,
  explain the *why*, push detail to the docs; a changed-parameters table + a steady-state-lands table +
  an example macro-results table.
- **Family approval gates apply** (the OG family README): calibrate, edit, and commit locally
  freely — but launching solves beyond a quick SS check, pushing, PR-opening, and anything
  fleet-scale are proposed and wait for the user's explicit call. Never merge.

### Preparing the calibration PR — what maintainers actually ask for [PHL #63 review, jdebacker]

- **Register: the PR reports what was done; the docs carry the discussion.** State each change and
  its anchor in a line or two ("unmodeled recurring revenue is carried by the nearest-equivalent
  instruments: property-type taxes on the wealth tax, state-asset income on the CIT adjustment, fees
  on `tau_c`") and point to the calibration chapter for the derivation, the alternatives, and the
  caveats. Design-justification paragraphs ("worth review", "the honest carrier", why-not-X) belong
  in the PR **only when explicitly asking the maintainers to decide something** — otherwise they
  read as asking for a debate nobody requested. **[PHL #85 feedback]**
- **Always include the goodness-of-fit table** — the standard close for any calibration PR: every
  calibrated moment, `Model | Target | Source`, one row per anchor, revenue lines first, then the
  external/fiscal anchors. Read the model column from the solved SS pickle, never from memory:

  | Moment | Model | Target | Source |
  |---|---|---|---|
  | PIT/Y … each revenue instrument … | | | collections source (e.g. OECD RevStats) |
  | total revenue/Y | | | |
  | RM/Y, K_f/K, D/Y, D_f/D, r_gov | | | BSP/BTr-class anchors |

  Follow it with the tested block (suite count, SS RC error, TPI RC error vs tolerance, debt-path
  behavior vs target) and the reform percent-change table (Y/C/K/L/r/w by year + SS), the same
  format across the family (see PHL #68/#85).

- **Show the before/after of every calibrated object the PR changes — upfront, don't make them ask.**
  On PHL #63 the maintainer's first request was a *new-vs-old side-by-side of the `io_matrix`*. For each
  changed array/matrix (`io_matrix`, `gamma`, `Z`, tax params), put an old→new table in the PR (or a
  reply thread) with the largest shifts called out and explained *by mechanism* — e.g. household energy
  spending moving off manufacturing onto electricity (54%→4% / 11%→74%) because the value-added method
  traces demand to the industry that makes it, not to the numeraire. The diff of a packaged JSON is
  unreadable; the side-by-side is how a reviewer verifies the change does what you claim.
- **Pre-empt the `gamma_g` question.** The maintainer flagged that the SAM books all non-labor income as
  capital with no public-capital attribution, so subtracting `gamma_g` implicitly from *labor* is wrong.
  State the construction explicitly: rescale the SAM's total capital shares to the economy-wide total,
  then subtract `gamma_g` so public capital comes out of *capital* (the SAM measures labor's share
  well). If `gamma_g = 0` (e.g. ZAF), say so — private = total, no carve-out — so the reviewer needn't
  raise it.
- **PR-explanation visuals are not docs visuals.** The maintainer asked that a figure's "what's changing
  in this PR" annotation (a dashed old-vs-new line) be *removed from the version committed to the docs*.
  Keep delta/before-after annotations in the PR conversation; the docs figure shows the calibrated state
  cleanly, because the docs describe the calibration as it *is*, not the PR's delta.
- **Explain derived mechanical corrections in plain language a non-specialist can follow.** A non-obvious
  fix (the chi/`p_tilde` units conversion; a Z-level factor rescale) needs: what was off, the arithmetic
  that causes it, and that the constant is *derived, not fitted*. Same for version-driven fixes — if an
  ogcore bump broke the example and you regenerated demographics/params to fix it, say so and give the
  before/after residual-constraint numbers.

## End-to-end sequence for a new country

*Mechanics used throughout:* solve/run via `uv run python examples/run_og_<xxx>.py` (baseline +
reform + output tables); the earnings tilt is solved inside `income.py`'s
`get_e_interp(gini_to_match=...)`; and dashboard moments are read from the solved output objects with
`ogcore.utils.safe_read_pickle` on `.../OUTPUT_BASELINE/SS/SS_vars.pkl`, `.../TPI/TPI_vars.pkl`, and
`model_params.pkl` (then form ratios like `K_f/Y`, `C/Y`, revenue/GDP).

0a. **Two dashboards, built together: the near-term fiscal PATH and the steady state.** The path
   panel (debt, primary balance, revenue, public investment vs actuals + the country's program) is
   the falsifiable one and catches the errors the SS cannot see — above all a wrong
   `initial_debt_ratio`, which the SS scores against a policy anchor rather than data. Do not defer
   it to "after the SS validates". **[net-new: JPN]**
0. **Step zero, before any parameter is touched: write the moment x lever table** from OG-Core's own
   equations (see *Step zero*), and build the validation dashboard from it — one row per moment you
   intend to hit, and a row for every component of the resource constraint. **Dashboard first, tuning
   second.** OG-JPN did it the other way round and a placeholder `zeta_K` survived fourteen tuning
   rounds because `K_f/K` was never scored. **[net-new: JPN]**
1. Bootstrap from the closest sibling repo; **immediately fix the copied `country_id`, package name,
   and `egg-info`** (the #1 copy-paste regression).
2. Environment: `uv sync --extra dev`; confirm the resolved ogcore in `uv.lock` matches the EAPD
   siblings; run the preflight.
3. Demographics: set `country_id` (named constant) + add the regression test; solve, check SS
   population growth is sane.
4. Earnings: set the country's earnings-concept Gini (WID, matching the US reference concept); solve
   the tilt scalar.
5. Macro block: debt (initial measured, SS anchored), `zeta_K` (Chinn-Ito prior, tuned to the IIP
   foreign-capital level — re-validate after step 7), world rate (open vs distressed fork), `g_y`
   window (named constants), remittances if material (personal measure; model-consistent `g_RM`
   path; `eta_RM` from survey concentration) / aid, `r_gov` re-anchored to the treasury's effective
   real rate, the centered debt-elastic premium, `initial_Kg_ratio` if `gamma_g > 0`.
6. Capital share: `1 − labor_share`, Gollin-adjusted if agrarian/informal; **remove gamma from the
   live-API path** so it can't be clobbered.
7. Taxes — anchor to the OECD Revenue Statistics country note by instrument: for PIT, prefer a
   **progressive form fit to the statutory schedule** over a flat rate whenever a schedule exists —
   **GS by default** (φ0 = statutory top rate, φ1 to the shape, φ2 to collections; floors ETR at 0);
   take VAT/CIT/payroll/bequest as effective rates from collections (payroll is *additive* to the
   ETR function — audit the combined take; bequest effective is typically 1–2 orders below
   statutory); capture recurring non-tax and property-type revenue on the nearest-margin instruments
   (wealth tax / CIT adjustment / `tau_c`); close the budget identity
   (`alpha_G = revenue − pb* − alpha_T − alpha_I`); pick the informality rung the data supports.
8. `chi_n`: leave at the US values but **document it as uncalibrated**, or re-tilt to an hours target.
9. Validate: build the steady-state dashboard; check revenue by instrument; add the value-pinning test.
   **Run a baseline TPI too** — the steady state consumes one number from each time-varying path (its
   terminal value), so an entire mis-specified path is invisible to it. On JPN a wrong demographic
   window survived eleven steady-state tuning rounds with every fiscal moment inside 0.2pp of GDP, and
   one transition run caught it.
9b. **Save a warm-start seed** from the first solve that converges, and ship it. Without one the next
   port of this calibration may not solve at all — see the warm-start section.
10. (Optional) Multi-industry: source the SAM (national SUTs → UNU-WIDER/IFPRI → modeled databases;
    vintage matched to the LFS year); assert the concordances partition it; build the 5 SAM inputs,
    numeraire industry last; try the direct solve first (`nu≈0.2`; continuation only as fallback);
    apply the chi units conversion, then a Z-level rescale if `factor` is still off; verify
    single↔multi agreement via the comparison dashboard and the same-reform acceptance test.
11. Wrap up: `make format`, `pytest -m 'not local'`, CHANGELOG entry (before→after + citation), docs
    with glue-from-JSON. Ask before pushing; ask before the PR.

## Related skills

- `og-run` — actually launching the baseline and reform solves.
- `og-run-preflight` — the go/no-go check before any solve.
- `calibration-provenance` — tracing one parameter to its source.
- `muiogo-explain` — explaining the calibration to a person.
- `og-clews-linked-run` — coupling the calibrated model to a CLEWs energy scenario.

These live in the MUIOGO-AI collection; if one is not available to you,
do the job directly and say which skill would have covered it.
