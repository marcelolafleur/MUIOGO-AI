# Country-data research protocol

## Source order

Search in this order unless the variable requires specialist engineering data:

1. national statistics office;
2. responsible ministry, regulator, system operator, mapping agency, inventory,
   census, or administrative register;
3. official national plans and legislation for genuine policy constraints;
4. primary international institutions such as FAO, IRENA, IEA, World Bank,
   UN agencies, or multilateral development banks;
5. peer-reviewed or authoritative engineering sources;
6. transparent regional/global proxies.

Prefer the source that measures the model concept, not merely the source with
the most convenient number.

## Evidence capture

For each source retain:

- provider, product, edition, publication date, and access date;
- geography, reference period, variable definition, and published unit;
- exact page, table, sheet, cell, API query, or map layer;
- URL, license, local file, and SHA-256 when retained;
- extraction/transcription method and any blocked-download limitation.

Retain publisher bytes when permitted. If only a normalized transcription can
be retained, identify it as a transcription and preserve the exact official
locator. Do not assign the transcription's checksum to the unavailable source
file.

## Concept and boundary checks

Before using a number, verify:

- stock versus flow versus capacity;
- gross versus net, input versus output, and useful versus final energy;
- installed versus dependable/available capacity;
- withdrawal versus consumption and renewable flow versus storage;
- land cover versus land use and administrative versus model geography;
- product weight versus processed equivalent;
- nominal versus real currency, base year, and exchange rate;
- annual, seasonal, timeslice, national, regional, and cluster scope.

## Demand drivers and annualization

For exogenous demand and intensity series, prefer transparent physical
identities—such as population × per-capita demand × coverage × loss adjustment,
or area × event intensity × annual frequency ÷ system efficiency—over
unexplained growth rates. Clearly distinguish unique service area or stock from
annually repeated activity. Keep country-specific values, formulas, assumptions,
and supporting sources in the country evidence and calculation notes rather
than in this generic guidance.

When future substitution is part of the question, express demand as the service
required—such as useful energy, passenger-kilometres, tonne-kilometres, or
delivered water—and let eligible carriers and technologies compete. Treat
historical carrier use as calibration evidence unless a carrier-fixed demand is
itself the intended policy boundary.

## Missing, zero, and inapplicable observations

Classify every absent observation as `observed_zero`,
`structurally_inapplicable`, `unreported`, or `unavailable`. A blank or omitted
value is not evidence of zero. Encode zero or remove a physical branch only when
the source definition and independent country evidence support that
interpretation; otherwise retain the uncertainty as a documented gap.

## Transformations

Write every nontrivial transformation in `CALCULATIONS.csv` using actual input
values and units. Record crosswalks, interpolation, extrapolation, currency
conversion, deflation, unit conversion, spatial allocation, reconciliation,
rounding, and uncertainty assumptions. Code may reproduce the arithmetic but
does not replace a readable formula.

## Policy evidence

Distinguish legal limits, adopted targets, programme implementation capacity,
technical potential, economic potential, and observed outcomes. A programme
target can justify a labelled policy envelope; it is not automatically a
measurement of realized annual change.

## Fallback proxies

Use a proxy only after recording why better evidence is unavailable. State the
central value, unit, transfer rationale, materiality, limitations, and upgrade
source. Prefer a simple transparent proxy over false precision.

## Historical benchmarks

Keep observed outcomes in a diagnostic inventory. Compare after solving and
report mismatches. Never back-solve a parameter from an outcome unless the
derived quantity is itself the measured physical concept and the derivation is
independent of the model result.
