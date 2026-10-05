# Closed resource-account calibration

## Scope

Use this protocol for land, water, biomass, fisheries, minerals, emissions
budgets, or any subsystem whose classes or uses share a fixed or finite total.

## 1. Define the boundary

Record geography, reference period, unit, included and excluded classes,
source total, model control total, and whether the source represents stock,
gross flow, net flow, capacity, potential, or use.

Never silently mix terrestrial area with administrative or maritime area,
renewable flow with storage, or gross withdrawal with consumptive use.

## 2. Build an explicit crosswalk

Map every source class to exactly one model class or a documented exclusion.
Record aggregation, scaling, reconciliation, and rounding calculations. Verify:

`sum(mapped source classes) + exclusions = published source total`

and, after any declared model-boundary reconciliation:

`sum(model base-year classes) = model account total`.

## 3. Initialize every class

Give each model class an explicit base-year value. A floor alone is not an
initialization equality when a rewarded class can absorb the residual. Use
base-year lower/upper equality where the observed stock is intended as the
initial condition.

## 4. Close every modeled year

Require an annual total equality or an equivalent complete stock-flow identity.
If unconstrained class activity can disappear, the account is not closed.

For every year verify:

`sum(class floors) <= total <= sum(class ceilings)`.

Then calculate every feasible residual destination. Do not rely on the solver
to reveal a missing class.

## 5. Separate stock from productive activity

Physical cover or available resource can exceed productive use. Represent the
difference explicitly as fallow, idle, reserve, storage, environmental flow, or
another defensible class. Bound bookkeeping routes so they cannot create an
unlimited new sink or resource.

## 6. State conversion scope precisely

Distinguish:

- fixed/protected stock;
- destination-specific eligible stock;
- unrestricted convertible stock;
- gross conversion versus net stock change;
- annual transition rate versus cumulative expansion envelope.

A forest-only eligibility ceiling must not restrict conversion to crops or
built-up land. A national eligibility fraction is not a parcel-suitability map.

## 7. Implement the claimed transition

These are not equivalent:

```text
stock[y] <= stock[base] + rate * (y - base)       # cumulative envelope
stock[y] - stock[y-1] <= rate                     # annual net increase
gross_conversion_to_stock[y] <= rate              # annual gross transition
```

Use an adjacent-year constraint when claiming an annual maximum. If the local
formulation cannot express it, label the implemented rule as a cumulative
envelope and record the limitation.

## 8. Verify serializer and index behavior

Numeric zero may mean disabled, active, or omitted depending on parameter and
exporter. Inspect generated data and the matrix. When a tiny positive sentinel
is required to preserve a bound, record its unit, maximum physical consequence,
and why exact zero disappeared.

Verify that a national cap is not instantiated independently per cluster or
mode. Never pro-rate by cluster merely because the model is clustered.

## 9. Pre-solve stress tests

Test analytically:

- all fixed values and base-year closure;
- all-year minimum and maximum feasible totals;
- rewarded/negative-cost class at its maximum;
- each protected class at its floor;
- unallocated/backstop/idle routes at their bounds;
- full release of destination-specific convertible stock;
- decline followed by rebound under any claimed annual rate.

## 10. Validate solved behavior

Report selected-year stocks, annual changes, binding bounds, residual routes,
productive versus idle quantities, total closure, objective effect, adjacent
sector effects, and known alternative optima. Solver optimality alone does not
establish a credible resource account.

## 11. Prove constraint representability

Write the intended identity with its actual region, technology, mode, year, and
timeslice indices, then map every term to the available constraint parameters.
Classify it as exact, approximate, or unsupported. A technology-level multiplier
is not exact when the required coefficient varies by mode. Include demand, trade,
capacity-linked flows, and other non-activity balance terms. Test each resource
account independently. If exact representation fails, record the gap or extend
the formulation; route reporting-only accounting to `add-environmental-accounting`.
