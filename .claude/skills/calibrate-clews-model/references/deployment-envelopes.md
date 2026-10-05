# Policy-neutral technology deployment envelopes

Use this pattern to represent how quickly a real construction, financing,
permitting, equipment-supply and grid-connection ecosystem can commission
capacity. The master rule in [non-forcing.md](non-forcing.md) remains
authoritative: constrain a continuing physical capability, never an endogenous
outcome merely because its historical value is known.

## Keep five quantities separate

| Quantity | Model meaning |
|---|---|
| Resource potential | Maximum usable stock, capacity or activity |
| Deployment envelope | Maximum capacity that can commission in one year |
| Committed-project allowance | Sourced, year-specific capacity already credibly deliverable |
| Replacement allowance | Headroom that prevents an entry ceiling from forcing stock retirement |
| Policy target | Scenario requirement; not evidence of delivery capability |

Do not use a resource potential or a policy target as an annual construction
rate. Apply the same physical deployment envelope to policy and non-policy
scenarios; add policy requirements separately.

## Classify the evidence and scope

Apply the skill's counterfactual test. A deployment envelope may be a
legitimate continuing physical constraint, but never select its value to make
modeled investment resemble an observed outcome. Include it in a coherent
sector wave when it materially affects sector representation; otherwise place
the isolated update in the calibration backlog.

Classify evidence explicitly:

1. domestic gross commissioning records, when available;
2. domestic net annual capacity additions;
3. current domestic project sizes, pipelines and delivery records;
4. international deployment only as an upper-bound reasonableness check; and
5. judgmental later-period scaling, labelled as an envelope rather than a
   forecast.

Net additions can understate gross commissioning when retirement occurs in
the same year. Do not copy a historical net maximum mechanically when better
gross or current-project evidence exists.

## Use a non-forcing annual formulation

For each technology and year after the preserved historical period, prefer:

```text
TAMaxCI[t,y] =
    max(finite_committed_allowance[t,y], expansion_envelope[t,y])
  + residual_retirement_allowance[t,y]
  + recycled_permitted_allowance[t,y]
```

This is an upper bound only. Add no capacity minimum, generation minimum,
activity bound, technology share or policy capacity total.

- Use `max`, not addition, when committed projects are already part of the
  industry's general delivery capability; this avoids double counting.
- Define residual retirement from the lossless inherited capacity trajectory,
  for example `max(0, RC[t,y-1] - RC[t,y])` when that matches the local stock
  representation.
- Recycle a genuine permitted allowance after the technology's operational
  life when replacement of endogenous vintages must remain possible.
- Start recycling no earlier than the first year in which the physical
  envelope applies.
- Preserve any finite, sourced committed-project allowance when it exceeds the
  general envelope.

Never recycle unlimited defaults or sentinels such as `9999`, `999999` or a
formulation-specific disabled-bound value. Determine sentinel semantics from
the active source and formulation. Recycling a default can silently remove the
constraint over the later horizon.

## Classify technology roles before assigning headroom

For every affected technology, record one of:

- expansion-capable physical generation;
- inherited physical stock only;
- combined inherited-field repowering and greenfield representation; or
- unavailable before a sourced industry-readiness date.

An inherited-stock-only technology normally retains its residual-capacity
path but receives no expansion allowance. Do not infer this role from `_OLD`
or another name fragment. If an `_OLD` technology is also the model's only
representation of a resource, decide explicitly whether it must carry both
repowering and greenfield headroom.

A zero upper bound is active and switches entry off. Use one before an
industry-readiness date only when the absence of delivery capability is a
continuing real-world constraint, not merely because historical deployment was
zero.

## Do not confuse permission with economic choice

Replacement headroom prevents forced retirement; it does not force or make
replacement economic. If the optimizer still abandons a persistent field or
plant class, investigate costs, performance, fuel/resource representation and
technology structure. A combined greenfield/repowering technology may suppress
repowering when both activities share one greenfield cost. Record that
representation gap; do not add a minimum to conceal it.

## Validate deterministically before solving

Add no new general validator or optimizer run. Extend the change's existing
source-diff and calculation checks to prove:

- every preserved historical cell is unchanged;
- every changed technology-year equals the documented formula;
- committed allowances are finite, sourced and not double-counted;
- sentinel/default values never enter recycling;
- residual retirements and recycled vintages cover the full horizon;
- inherited-stock-only technologies receive no unintended expansion;
- scenario overrides remain unchanged and inherit the BASE physical envelope
  where the scenario system uses sparse overrides; and
- no minimum, share, activity bound or cross-technology cap was introduced.

After solving, inspect binding annual ceilings and duals, adjacent-year entry,
capacity and activity, and substitution into other technologies.

## Report realism by dimension

Say that a deployment envelope improves construction-timing realism when the
evidence supports that conclusion. Do not infer that the resulting generation
mix, emissions path or policy trajectory is therefore realistic. A more
credible build rate can expose separate cost, dispatch, resource or technology
representation problems; report those rather than smoothing them with forcing
constraints.
