# Retiring inactive but referenced branches

Use this procedure only when an object remains referenced in model inputs but is
demonstrably outside the active country representation. Unreferenced,
value-neutral cleanup belongs in `clews-model-fix`.

## Preconditions

Before deletion, establish all of the following with exact identifier matching:

1. Inventory every reference to the commodity, technology, and linked producer
   or consumer objects across source parameter JSON and `genData.json`.
2. Confirm the branch has no intended demand, consumer, conversion route,
   reserve role, policy constraint, or accounting role inside the country
   boundary. Treat terminal environmental accounts separately.
3. Confirm zero activity, investment, capacity contribution, emissions, and cost
   throughout the solved horizon. Interpret default or sentinel values through
   the local equations instead of assuming that a large bound proves activity.
4. Record why the branch is unsupported or duplicated, which identifiers will
   be retired, and which retained route represents the same physical service, if
   any.

If any condition is unresolved, retain the branch and record a gap.

## Implement and preserve lineage

Create a coherent calibration-package change with `change_type` set to
`object_retirement`. Declare `retired_object_ids`, the reference-inventory
artifact, and the inactivity-evidence artifact. Start from the complete current
provenance ledger and retained evidence; supersede retired model-map records and
add a change record rather than deleting history.

Remove the complete inactive lineage from source inputs and regenerate through the
normal application chain. Include all retirements in the current calibration
wave and verify them from that wave's single solve; do not solve once per
retirement. Never create dummy demand, supply,
disposal, or activity merely to suppress a missing-target warning.

## Verify and promote

Verify that:

- every declared reference was removed and no substring or similarly named
  identifier was touched;
- the targeted missing-target findings disappeared without creating new ones;
- the generated model and result tables contain no retired identifiers;
- the fresh solve succeeds; and
- the baseline comparison filters only the exact retired identifiers, checks
  core annual outcomes first, and reports affected technologies and years.

Use a comparison-rules file such as:

```json
{
  "retired_values": ["TEC_OLD", "COM_OLD"],
  "equivalence_groups": {"t": {"SAME_SERVICE": ["TEC_A", "TEC_B"]}}
}
```

Classify the comparison as exact parity, structural parity with an
alternate-optimum candidate, or material change. Promotion of an
alternate-optimum candidate requires a recorded acceptance decision, rationale,
and the comparison artifact; the comparator does not accept it automatically.
