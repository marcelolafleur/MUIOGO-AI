# CLEWs connectivity and basic-realism audit

## Purpose

Find model components that are syntactically present but physically,
economically, temporally, spatially, or accounting-wise disconnected. Treat
automated findings as candidates requiring equation and role review.

## Declare roles before judging

Do not infer behavior from technology or commodity names. Build an explicit
role register for material technologies and modes:

- `physical_stock`: requires capacity, survival, and a material input/output;
- `conversion`: converts one modeled commodity to another;
- `resource_supply`: introduces a finite or priced primary resource;
- `pass_through`: intentionally relays a commodity without representing stock;
- `demand`: converts a resource into an exogenous final service;
- `accounting`: carries a balance or reporting flow;
- `backstop`: prevents infeasibility and must be deliberately costly/bounded;
- `environmental_sink`: terminates a reported environmental flow.

Use `assets/connectivity-rules.template.json` to register expected input links,
legitimate terminal commodities, and reviewed exemptions.

## Audit dimensions

### Commodity graph

Flag commodities that have:

- positive production but no consumer or declared terminal/reporting role;
- positive consumption but no producer or declared exogenous source;
- neither production nor consumption;
- production and consumption only inside an isolated cycle with no resource
  origin or final demand.

### Physical coupling

Test material relationships explicitly. Examples, where represented:

- crop output requires land; irrigated crop activity also requires water;
- water withdrawal originates in surface water, groundwater, precipitation,
  storage, reuse, desalination, or another declared source;
- thermal generation consumes fuel and, if cooling water is in scope, connects
  to the cooling-water balance;
- transport service consumes a fuel or electricity through a vehicle stock;
- extraction is bounded by reserves, annual potential, capacity, or price;
- land classes participate in one closed land boundary;
- emissions-producing activity connects to the emissions account.

Absence is not automatically an error when the linkage is outside the declared
model boundary. Document that boundary and its consequences.

### Unlimited-free supply

Investigate a useful-output mode when all of the following are true:

1. it has no material input;
2. variable cost is zero or negative;
3. capital and fixed cost are zero;
4. residual/new capacity or annual activity is effectively unbounded; and
5. no finite resource, availability, emissions, or user constraint limits it.

Imports, precipitation, environmental accounting, and pass-throughs may
legitimately have no physical input, but they still need a declared role and a
price, quantity, or accounting boundary that prevents unintended infinite use.

### Accounting residuals

For each fixed-total account, solve the arithmetic before optimization:

`residual[y] = total[y] - sum(fixed[y]) - sum(selected flexible[y])`

Identify which mode can receive it. Unallocated, other, idle/fallow, imports,
disposal, curtailment, or slack must never become an accidental sink merely
because every preferred class has a floor and one cheap route remains free.

Stress-test each rewarded or negative-cost class at its ceiling and every
protected class at its floor.

### Temporal coupling

Check that:

- residual capacity survives and retires over the correct years;
- new capacity vintages survive for their operational lives;
- annual policy rates use adjacent-year constraints when that is the claim;
- cumulative ceilings are labelled as cumulative;
- a stock cannot fall and rebound faster than a claimed annual transition rate;
- base-year equalities do not silently become permanent pins.

### Spatial and index scope

Read the generated constraint indices. A national quantity repeated for each
cluster, technology mode, region, season, or timeslice is not a national cap.
Require a sourced allocation or implement the bound once at national scope.

## Resolution hierarchy

For every material finding, choose one:

1. **Connect:** add the missing physical input/output or account relationship.
2. **Bound:** add a sourced finite stock, activity, capacity, potential, or
   transition constraint.
3. **Price:** add a sourced cost where quantity is intentionally elastic.
4. **Declare:** record a legitimate accounting, pass-through, terminal, or
   backstop role and prove it cannot distort the model.
5. **Defer:** record a gap, consequences, materiality, and replacement evidence.

Never repair a disconnection by pinning historical activity or shares.

## Required evidence

Retain the machine-readable audit, reviewed disposition for each finding, exact
source/model changes, generated-data proof, solve behavior, and schema-ledger
lineage. A clean graph alone does not prove physical adequacy; role review and
equation inspection remain mandatory.
