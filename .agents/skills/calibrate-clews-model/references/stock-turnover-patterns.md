# Stock, turnover and adoption patterns

## Interpret observations first

- A stock observation initializes capacity or an age cohort.
- A service observation belongs in final demand when it is genuinely
  exogenous.
- An activity observation is normally a benchmark, not a constraint.
- Sales and registrations bound annual entry; they do not directly prescribe
  utilization.
- A resource or policy limit is a model constraint only when its continued
  applicability and horizon are sourced.

Do not convert a historical flow into a temporary activity pin merely because
the model otherwise chooses a different technology.

## Trace the local capacity equations

Verify the active formulation rather than relying on these generic names:

- `CAa1`/`CAa2`: total capacity equals residual capacity plus surviving new
  capacity vintages.
- `CAa4`/`CAb1`: activity is limited by total capacity, capacity factors,
  availability and the capacity-to-activity unit.
- `NCC1`: total annual maximum new capacity investment limits
  `NewCapacity`.
- `EBa*`: commodity production/use and demand balances determine whether the
  stock can supply the required service.

Check mode, timeslice, year and scenario indexing in both source and generated
data.

## Represent inherited stock

Use the best available hierarchy:

1. unit-level commissioning and retirement dates;
2. age-cohort or survival distributions;
3. official stock total with a sourced aggregate retirement curve;
4. uniform-age retirement as an explicit, replaceable proxy assumption;
5. effective initial stock derived from a fresh, full-precision feasible
   result when no defensible physical mapping exists.

An effective stock must retain relevant capacity factors, availability,
timeslice profiles and capacity-to-activity conversion. It must not retain
the activity constraint used to infer it.

## Test the entire horizon

For every class and year, calculate the maximum useful service from:

- surviving residual capacity;
- surviving allowed new-capacity vintages;
- capacity and availability factors;
- capacity-to-activity units;
- output ratios and timeslice demand profiles.

Compare this envelope with demand before solving. A formula based only on
retirement of the initial stock can become infeasible when endogenous
vintages reach their operational lives.

If a source formulation uses exogenous per-technology investment ceilings, an
allowance may be recycled after the technology's operational life:

```text
ceiling[t,y] =
    initial-retirement allowance[y]
  + positive service-growth allowance[y]
  + ceiling[t,y - OperationalLife[t]]
```

This is conservative allowance recycling, not the retirement of actual
optimized investment. Document that it can overstate total market entry,
especially when each technology receives the same class allowance. Prefer
observed technology-specific sales or a performant aggregate-investment
formulation when available.

## Separate adoption from utilization

Stock and investment limits prevent instantaneous physical replacement.
They do not prevent the optimizer from changing utilization among surviving
technologies. Always audit adjacent-year:

- total class service;
- technology capacity shares;
- technology activity shares;
- binding adoption constraints and duals.

Remaining utilization changes indicate a need for technology-specific
utilization, availability, costs, operating restrictions or service-quality
evidence. Do not automatically turn them into activity-share constraints.

## Treat aggregate coupling as a performance risk

An exact class-wide sales cap can require user-defined constraints or a permit
commodity network. Both add cross-technology coupling and may degrade CBC
performance. Before adoption:

1. prove the proposed cap is physically and dimensionally correct;
2. inspect the added rows, columns and nonzeros;
3. include the minimal aggregate cap in the current calibration wave rather
   than creating separate comparison runs;
4. stop near twice the known-good runtime;
5. inspect whether the cap binds in that retained solve.

Do not keep a slow aggregate formulation merely because it is mathematically
valid.
