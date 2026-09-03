# CLEWs country catalog and manifests

The CLEWs side of country installation, mirroring how OG models solve it.

- `clews-repos.json` — the catalog: which repos ship portable MUIO cases
  (the CLEWs analogue of the OG installer's `repos.json`).
- `countries/<ISO3>.json` — one manifest per country: its cases (with roles
  and a recommended default), where the archives live, checksums, and its OG
  counterpart. These **overlay manifests** now serve only the installer's
  legacy path (a pinned MUIOGO older than the `/clews` install layer). A
  current MUIOGO reads a country repo directly — its `clews-country.json` if
  it has one, otherwise the repo's contents (a folder with a `SHA256SUMS` and
  MUIO archives is a version) — so nothing here has to be kept in step with
  the repos. MUIOGO's own register of repos is `scripts/clews-repos.json` in
  the MUIOGO repository; the copy here is the legacy path's.

**Matching**: ISO3 is the join key everywhere. The OG installer derives
`PHL` from `OG-PHL`; a CLEWs manifest declares `iso3: PHL`; the composed
installer's `--country PHL` resolves both sides plus link registration from
that one key. Nobody maintains a central mapping table.

Used by `scripts/install.sh` (`--clews`, `--country`, `--case`). Cases are
installed into MUIOGO headless through its own `/uploadCase` HTTP endpoint —
the same validated path the GUI's restore uses.
