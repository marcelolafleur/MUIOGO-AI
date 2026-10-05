#!/usr/bin/env python3
# GENERATED FILE - do not edit here.
# Source: skills/shared/provenance/provenance.py
# Regenerate: python scripts/sync_shared.py
# This local copy keeps the installed skill self-contained in Claude and Codex.
"""Validate a CLEWs provenance ledger.

One validator for the six-table ledger described in SCHEMA.md. Replaces
skills/build-clews-model/scripts/validate_provenance.py and
skills/add-fisheries-sector/scripts/validate_provenance.py.

    python provenance.py LEDGER_DIR [--stage scaffold|build|delivery]
                                    [--model-inputs DIR] [--json REPORT]

Exit status is 0 when the ledger passes and 1 when it fails.

Design rule: this validator never records a hash of its own output, never
re-hashes content that already sits inside another hashed artifact, and never
accepts a digest it has not compared against real bytes on disk.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

STAGES = ("scaffold", "build", "delivery")

LEDGER_TABLES = (
    "SOURCES.csv",
    "CALCULATIONS.csv",
    "ASSUMPTIONS.csv",
    "MODEL_MAP.csv",
    "GAPS.csv",
    "CHANGES.csv",
)

REQUIRED_COLUMNS: Dict[str, Tuple[str, ...]] = {
    "SOURCES.csv": (
        "source_id",
        "provider",
        "product",
        "edition",
        "reference_period",
        "geography",
        "variable",
        "source_unit",
        "exact_locator",
        "url",
        "access_date",
        "license",
        "sha256",
    ),
    "CALCULATIONS.csv": (
        "calculation_id",
        "formula",
        "source_ids",
        "assumption_ids",
        "input_calculation_ids",
        "input_values",
        "input_units",
        "output_value",
        "output_unit",
        "script_path",
        "script_version",
    ),
    "ASSUMPTIONS.csv": (
        "assumption_id",
        "statement",
        "central_value",
        "unit",
        "evidence_source_ids",
        "lower_bound",
        "upper_bound",
    ),
    "MODEL_MAP.csv": (
        "map_id",
        "model_file",
        "parameter",
        "entity",
        "mode",
        "scenario",
        "years",
        "value_or_expression",
        "model_unit",
        "evidence_ids",
        "superseded_by",
    ),
    "GAPS.csv": (
        "item",
        "why_absent",
        "upgrade_source",
    ),
    "CHANGES.csv": (
        "change_id",
        "date",
        "class",
        "description",
        "model_objects",
        "evidence_path",
        "map_rows_affected",
        "resolve_status",
        "author",
        "commit",
    ),
}

# Columns a ledger may carry without provoking an unknown-column warning.
OPTIONAL_COLUMNS: Dict[str, Tuple[str, ...]] = {
    "SOURCES.csv": ("local_file", "notes"),
    "CALCULATIONS.csv": ("notes",),
    "ASSUMPTIONS.csv": ("rationale", "notes"),
    "MODEL_MAP.csv": ("evidence_type", "notes"),
    "GAPS.csv": ("priority", "notes"),
    "CHANGES.csv": ("notes",),
}

ID_COLUMN: Dict[str, str] = {
    "SOURCES.csv": "source_id",
    "CALCULATIONS.csv": "calculation_id",
    "ASSUMPTIONS.csv": "assumption_id",
    "MODEL_MAP.csv": "map_id",
    "CHANGES.csv": "change_id",
}

ID_PREFIX: Dict[str, str] = {
    "SOURCES.csv": "SRC_",
    "CALCULATIONS.csv": "CALC_",
    "ASSUMPTIONS.csv": "ASM_",
    "MODEL_MAP.csv": "MAP_",
    "CHANGES.csv": "CHG_",
}

# Values that must not be blank, beyond the identifier itself.
REQUIRED_VALUES: Dict[str, Tuple[str, ...]] = {
    "SOURCES.csv": (
        "provider",
        "product",
        "reference_period",
        "variable",
        "source_unit",
        "exact_locator",
        "access_date",
    ),
    "CALCULATIONS.csv": ("formula", "output_value", "output_unit"),
    "ASSUMPTIONS.csv": ("statement", "central_value", "unit"),
    "MODEL_MAP.csv": (
        "model_file",
        "parameter",
        "value_or_expression",
        "model_unit",
        "evidence_ids",
    ),
    "GAPS.csv": ("item", "why_absent"),
    "CHANGES.csv": ("date", "class", "description", "resolve_status", "author"),
}

# Values worth a nudge but never a failure.
ADVISORY_VALUES: Dict[str, Tuple[str, ...]] = {
    "SOURCES.csv": ("edition", "geography", "license"),
    "CALCULATIONS.csv": ("input_values", "input_units"),
    "GAPS.csv": ("upgrade_source",),
    "CHANGES.csv": ("model_objects", "commit"),
}

SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_SEPARATORS = re.compile(r"[;,\s]+")
GLOB_CHARS = ("*", "?", "[")

CHANGE_CLASSES = ("A", "B", "C")
RESOLVE_STATUSES = ("objective_unchanged", "resolve_required", "resolved")
EVIDENCE_TYPES = ("direct", "derived", "estimated")

_ID_PATTERNS = {
    table: re.compile(r"^" + re.escape(prefix) + r"[A-Za-z0-9][A-Za-z0-9._-]*$")
    for table, prefix in ID_PREFIX.items()
}


def split_ids(value: Optional[str]) -> List[str]:
    """Split a reference list on semicolons, commas or whitespace."""
    return [item for item in ID_SEPARATORS.split((value or "").strip()) if item]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_iso_date(value: str) -> bool:
    if not ISO_DATE_RE.match(value):
        return False
    year, month, day = (int(part) for part in value.split("-"))
    try:
        datetime.date(year, month, day)
    except ValueError:
        return False
    return True


def unsafe_relative_path(value: str) -> bool:
    candidate = Path(value)
    return candidate.is_absolute() or ".." in candidate.parts


def read_table(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    """Read a CSV into stripped dict rows, dropping wholly blank lines.

    Each row carries a ``_line`` key with its physical line number.
    """
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, restkey="_extra")
        fields = list(reader.fieldnames or [])
        rows: List[Dict[str, str]] = []
        for raw in reader:
            line = reader.line_num
            row: Dict[str, str] = {}
            extra = False
            for key, value in raw.items():
                if key is None or key == "_extra":
                    extra = True
                    continue
                if isinstance(value, list):
                    extra = True
                    value = " ".join(str(item) for item in value)
                row[key] = (value or "").strip()
            if not any(row.values()):
                continue
            row["_line"] = str(line)
            row["_extra"] = "1" if extra else ""
            rows.append(row)
    return fields, rows


def populated_csv(path: Path) -> bool:
    """True when a CSV has a header and at least one non-blank data row."""
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle)
            try:
                next(reader)
            except StopIteration:
                return False
            for row in reader:
                if any((cell or "").strip() for cell in row):
                    return True
    except (OSError, csv.Error, UnicodeDecodeError):
        return False
    return False


class LedgerValidator:
    """Accumulates failures and warnings for one ledger directory."""

    def __init__(
        self,
        ledger_dir: Path,
        stage: str = "build",
        model_inputs: Optional[Path] = None,
        required_inputs: Optional[Sequence[str]] = None,
        allow_inherited_coverage_gaps: bool = False,
    ) -> None:
        self.ledger_dir = ledger_dir
        self.stage = stage
        self.model_inputs = model_inputs
        self.required_inputs = [str(value) for value in (required_inputs or [])]
        self.allow_inherited_coverage_gaps = allow_inherited_coverage_gaps
        self.failures: List[str] = []
        self.warnings: List[str] = []
        self.fields: Dict[str, List[str]] = {}
        self.rows: Dict[str, List[Dict[str, str]]] = {}
        self.ids: Dict[str, Set[str]] = {}
        self.evidence_types: Dict[str, str] = {}
        self.verified_digests = 0
        self.coverage: Dict[str, object] = {}

    # ---------------------------------------------------------------- helpers

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    @staticmethod
    def where(table: str, row: Dict[str, str], identifier: str = "") -> str:
        label = " ".join((identifier or "<no id>").split())
        if len(label) > 60:
            label = label[:57] + "..."
        return "{0}:{1} {2}:".format(table, row.get("_line", "?"), label)

    def row_id(self, table: str, row: Dict[str, str]) -> str:
        column = ID_COLUMN.get(table)
        if not column:
            return row.get("item", "") or "<no id>"
        return row.get(column, "") or "<no id>"

    # ------------------------------------------------------------ stage 1: io

    def load(self) -> None:
        if not self.ledger_dir.is_dir():
            self.fail("ledger directory does not exist: {0}".format(self.ledger_dir))
            return
        for table in LEDGER_TABLES:
            path = self.ledger_dir / table
            if not path.is_file():
                self.fail("missing ledger table: {0}".format(table))
                continue
            try:
                fields, rows = read_table(path)
            except (OSError, csv.Error, UnicodeDecodeError) as exc:
                self.fail("cannot read {0}: {1}".format(table, exc))
                continue
            self.fields[table] = fields
            self.rows[table] = rows
            self.check_columns(table, fields, rows)

    def check_columns(
        self, table: str, fields: Sequence[str], rows: Sequence[Dict[str, str]]
    ) -> None:
        required = REQUIRED_COLUMNS[table]
        missing = [column for column in required if column not in fields]
        if missing:
            self.fail(
                "{0}: missing required columns: {1}".format(table, ", ".join(missing))
            )
        duplicates = sorted({name for name in fields if list(fields).count(name) > 1})
        if duplicates:
            self.fail(
                "{0}: duplicate header columns: {1}".format(
                    table, ", ".join(duplicates)
                )
            )
        known = set(required) | set(OPTIONAL_COLUMNS.get(table, ()))
        unknown = [column for column in fields if column and column not in known]
        if unknown:
            self.warn(
                "{0}: unknown columns tolerated but not validated: {1}".format(
                    table, ", ".join(unknown)
                )
            )
        if any(row.get("_extra") for row in rows):
            self.warn(
                "{0}: at least one row has more fields than the header".format(table)
            )

    # -------------------------------------------------------- stage 2: rows

    def check_identifiers(self) -> None:
        for table, column in ID_COLUMN.items():
            rows = self.rows.get(table)
            if rows is None:
                continue
            pattern = _ID_PATTERNS[table]
            prefix = ID_PREFIX[table]
            seen: Set[str] = set()
            for row in rows:
                value = row.get(column, "")
                if not value:
                    self.fail(
                        "{0}:{1}: {2} is blank".format(
                            table, row.get("_line", "?"), column
                        )
                    )
                    continue
                if value in seen:
                    self.fail(
                        "{0}:{1}: duplicate {2} {3}".format(
                            table, row.get("_line", "?"), column, value
                        )
                    )
                else:
                    seen.add(value)
                if not pattern.match(value):
                    self.fail(
                        "{0}:{1}: {2} {3} must match {4}<token>".format(
                            table, row.get("_line", "?"), column, value, prefix
                        )
                    )
            self.ids[table] = seen

        # GAPS.csv has no identifier column; item is its de-facto key.
        seen_items: Set[str] = set()
        for row in self.rows.get("GAPS.csv", []):
            item = row.get("item", "")
            if item and item in seen_items:
                self.fail(
                    "GAPS.csv:{0}: duplicate item {1}".format(
                        row.get("_line", "?"), item
                    )
                )
            elif item:
                seen_items.add(item)

    def check_required_values(self) -> None:
        for table, columns in REQUIRED_VALUES.items():
            rows = self.rows.get(table)
            if rows is None:
                continue
            for row in rows:
                identifier = self.row_id(table, row)
                for column in columns:
                    if column not in self.fields.get(table, []):
                        continue  # already reported as a missing column
                    if not row.get(column, ""):
                        self.fail(
                            "{0} {1} is blank".format(
                                self.where(table, row, identifier), column
                            )
                        )
        for table, columns in ADVISORY_VALUES.items():
            rows = self.rows.get(table)
            if rows is None:
                continue
            for row in rows:
                identifier = self.row_id(table, row)
                for column in columns:
                    if column not in self.fields.get(table, []):
                        continue
                    if not row.get(column, ""):
                        self.warn(
                            "{0} {1} is blank".format(
                                self.where(table, row, identifier), column
                            )
                        )

    def check_sources(self) -> None:
        for row in self.rows.get("SOURCES.csv", []):
            identifier = self.row_id("SOURCES.csv", row)
            where = self.where("SOURCES.csv", row, identifier)
            access_date = row.get("access_date", "")
            if access_date and not is_iso_date(access_date):
                self.fail(
                    "{0} access_date {1} is not an ISO date (YYYY-MM-DD)".format(
                        where, access_date
                    )
                )
            url = row.get("url", "")
            local_file = row.get("local_file", "")
            if not url and not local_file:
                self.fail(
                    "{0} has neither url nor local_file; the source is unreachable".format(
                        where
                    )
                )
            self.check_source_digest(row, where)

    def check_source_digest(self, row: Dict[str, str], where: str) -> None:
        """Verify a retained evidence file against its recorded digest.

        A digest is only ever accepted after the named file has been opened and
        hashed. A digest with no file to compare against is a failure, not a
        pass, because a format-only check verifies nothing.
        """
        digest = row.get("sha256", "")
        if digest and not SHA256_RE.match(digest):
            self.fail("{0} sha256 must be 64 hex characters".format(where))
            return
        digest = digest.lower()

        candidate = row.get("local_file", "")
        column = "local_file"
        if not candidate:
            url = row.get("url", "")
            looks_remote = "://" in url or url.lower().startswith(
                ("mailto:", "doi:", "www.")
            )
            if url and not looks_remote:
                candidate = url
                column = "url"

        if not candidate:
            if digest:
                self.fail(
                    "{0} records a sha256 but names no local evidence file; a digest "
                    "that is never compared against a file is not a check".format(where)
                )
            return

        if unsafe_relative_path(candidate):
            self.fail(
                "{0} {1} must be a ledger-relative path without '..': {2}".format(
                    where, column, candidate
                )
            )
            return

        path = self.ledger_dir / candidate
        if not path.is_file():
            if digest:
                self.fail(
                    "{0} retained evidence file is missing: {1}".format(
                        where, candidate
                    )
                )
            elif column == "local_file":
                self.fail(
                    "{0} local_file does not exist: {1}".format(where, candidate)
                )
            else:
                self.warn(
                    "{0} url has no scheme and is not a file in the ledger; state "
                    "whether the source is public or restricted".format(where)
                )
            return

        if not digest:
            self.fail(
                "{0} retained evidence file {1} records no sha256".format(
                    where, candidate
                )
            )
            return

        try:
            actual = sha256_file(path)
        except OSError as exc:
            self.fail(
                "{0} cannot read retained evidence {1}: {2}".format(
                    where, candidate, exc
                )
            )
            return
        if actual != digest:
            self.fail(
                "{0} sha256 mismatch for {1}: recorded {2}, file is {3}".format(
                    where, candidate, digest, actual
                )
            )
        else:
            self.verified_digests += 1

    def check_calculations(self) -> None:
        for row in self.rows.get("CALCULATIONS.csv", []):
            identifier = self.row_id("CALCULATIONS.csv", row)
            where = self.where("CALCULATIONS.csv", row, identifier)
            sources = split_ids(row.get("source_ids"))
            assumptions = split_ids(row.get("assumption_ids"))
            inputs = split_ids(row.get("input_calculation_ids"))
            if not (sources or assumptions or inputs):
                self.fail(
                    "{0} needs at least one source_id, assumption_id or "
                    "input_calculation_id".format(where)
                )
            if identifier in inputs:
                self.fail("{0} lists itself in input_calculation_ids".format(where))
            if row.get("script_path") and not row.get("script_version"):
                self.fail(
                    "{0} script_version is required when script_path is used".format(
                        where
                    )
                )
            if row.get("script_version") and not row.get("script_path"):
                self.warn(
                    "{0} script_version is recorded without a script_path".format(where)
                )

    def check_assumptions(self) -> None:
        for row in self.rows.get("ASSUMPTIONS.csv", []):
            identifier = self.row_id("ASSUMPTIONS.csv", row)
            where = self.where("ASSUMPTIONS.csv", row, identifier)
            lower = row.get("lower_bound", "")
            upper = row.get("upper_bound", "")
            if bool(lower) != bool(upper):
                self.warn(
                    "{0} has only one of lower_bound/upper_bound; record both or "
                    "neither".format(where)
                )
            central = row.get("central_value", "")
            try:
                numbers = [float(value) for value in (lower, central, upper) if value]
            except ValueError:
                continue  # non-numeric assumptions are legitimate
            if len(numbers) == 3 and not numbers[0] <= numbers[1] <= numbers[2]:
                self.fail(
                    "{0} bounds do not bracket central_value: {1} <= {2} <= {3}".format(
                        where, lower, central, upper
                    )
                )

    def check_model_map(self) -> None:
        for row in self.rows.get("MODEL_MAP.csv", []):
            identifier = self.row_id("MODEL_MAP.csv", row)
            where = self.where("MODEL_MAP.csv", row, identifier)
            model_file = row.get("model_file", "")
            if model_file:
                if any(char in model_file for char in GLOB_CHARS):
                    self.fail(
                        "{0} model_file must name one file, not a pattern: {1}".format(
                            where, model_file
                        )
                    )
                elif unsafe_relative_path(model_file):
                    self.fail(
                        "{0} model_file must be a relative path without '..': "
                        "{1}".format(where, model_file)
                    )
            evidence = split_ids(row.get("evidence_ids"))
            derived = self.derive_evidence_type(evidence)
            if identifier != "<no id>":
                self.evidence_types[identifier] = derived
            if evidence and not derived:
                self.fail(
                    "{0} evidence_ids resolve to no source, calculation or "
                    "assumption".format(where)
                )
            declared = row.get("evidence_type", "")
            if declared:
                normalized = declared.strip().lower()
                if normalized not in EVIDENCE_TYPES:
                    self.warn(
                        "{0} evidence_type {1} is not one of {2}; the type is derived "
                        "from evidence_ids".format(
                            where, declared, "/".join(EVIDENCE_TYPES)
                        )
                    )
                elif derived and normalized != derived:
                    self.fail(
                        "{0} evidence_type says {1} but evidence_ids make it "
                        "{2}".format(where, normalized, derived)
                    )

    def derive_evidence_type(self, evidence: Sequence[str]) -> str:
        """Derive direct/derived/estimated from the evidence IDs themselves.

        A calculation anywhere in the lineage makes the value derived; failing
        that an assumption makes it estimated; a source-only row is direct.
        """
        has_calculation = any(
            item in self.ids.get("CALCULATIONS.csv", set()) for item in evidence
        )
        has_assumption = any(
            item in self.ids.get("ASSUMPTIONS.csv", set()) for item in evidence
        )
        has_source = any(
            item in self.ids.get("SOURCES.csv", set()) for item in evidence
        )
        if has_calculation:
            return "derived"
        if has_assumption:
            return "estimated"
        if has_source:
            return "direct"
        return ""

    def check_changes(self) -> None:
        map_rows = {
            row.get("map_id", ""): row for row in self.rows.get("MODEL_MAP.csv", [])
        }
        affected_by_change: Dict[str, Set[str]] = {}
        for row in self.rows.get("CHANGES.csv", []):
            identifier = self.row_id("CHANGES.csv", row)
            where = self.where("CHANGES.csv", row, identifier)
            date = row.get("date", "")
            if date and not is_iso_date(date):
                self.fail(
                    "{0} date {1} is not an ISO date (YYYY-MM-DD)".format(where, date)
                )
            change_class = row.get("class", "").strip().upper()
            if change_class and change_class not in CHANGE_CLASSES:
                self.fail(
                    "{0} class must be one of {1}".format(
                        where, ", ".join(CHANGE_CLASSES)
                    )
                )
            resolve_status = row.get("resolve_status", "").strip().lower()
            if resolve_status and resolve_status not in RESOLVE_STATUSES:
                self.warn(
                    "{0} resolve_status {1} is not one of {2}".format(
                        where, resolve_status, "/".join(RESOLVE_STATUSES)
                    )
                )
            commit = row.get("commit", "")
            if commit and not COMMIT_RE.match(commit.lower()):
                self.fail(
                    "{0} commit {1} is not a 7-40 character hex revision".format(
                        where, commit
                    )
                )
            affected = split_ids(row.get("map_rows_affected"))
            if identifier != "<no id>":
                affected_by_change.setdefault(identifier, set()).update(affected)
            if change_class != "A":
                continue

            if not row.get("evidence_path", ""):
                self.fail(
                    "{0} class=A must name the audit artifact that proves the "
                    "precondition held (evidence_path)".format(where)
                )
            else:
                evidence_path = row.get("evidence_path", "")
                if unsafe_relative_path(evidence_path):
                    self.warn(
                        "{0} evidence_path is absolute or escapes the ledger: "
                        "{1}".format(where, evidence_path)
                    )
                elif not (self.ledger_dir / evidence_path).exists():
                    self.warn(
                        "{0} evidence_path is not present under the ledger "
                        "directory: {1}".format(where, evidence_path)
                    )
            if resolve_status and resolve_status != "objective_unchanged":
                self.warn(
                    "{0} class=A normally records resolve_status="
                    "objective_unchanged, not {1}".format(where, resolve_status)
                )
            for map_id in affected:
                target = map_rows.get(map_id)
                if target is None:
                    continue  # reported by the cross-reference pass
                if not target.get("superseded_by", ""):
                    self.fail(
                        "{0} class=A references MODEL_MAP row {1}, which is still "
                        "active; set its superseded_by to {2}".format(
                            where, map_id, identifier
                        )
                    )
                elif target.get("superseded_by", "") != identifier:
                    self.warn(
                        "{0} class=A references MODEL_MAP row {1}, which is "
                        "superseded by {2} instead".format(
                            where, map_id, target.get("superseded_by", "")
                        )
                    )
        for map_id, row in map_rows.items():
            superseded_by = row.get("superseded_by", "")
            if not superseded_by or not map_id:
                continue
            listed = affected_by_change.get(superseded_by)
            if listed is not None and map_id not in listed:
                self.warn(
                    "{0} superseded_by {1}, but that change does not list this row in "
                    "map_rows_affected".format(
                        self.where("MODEL_MAP.csv", row, map_id), superseded_by
                    )
                )

    # ------------------------------------------------- stage 3: cross-refs

    def check_references(self) -> None:
        checks = (
            ("MODEL_MAP.csv", "evidence_ids", ("SOURCES.csv", "CALCULATIONS.csv", "ASSUMPTIONS.csv")),
            ("MODEL_MAP.csv", "superseded_by", ("CHANGES.csv",)),
            ("CALCULATIONS.csv", "source_ids", ("SOURCES.csv",)),
            ("CALCULATIONS.csv", "assumption_ids", ("ASSUMPTIONS.csv",)),
            ("CALCULATIONS.csv", "input_calculation_ids", ("CALCULATIONS.csv",)),
            ("ASSUMPTIONS.csv", "evidence_source_ids", ("SOURCES.csv",)),
            ("CHANGES.csv", "map_rows_affected", ("MODEL_MAP.csv",)),
        )
        for table, column, targets in checks:
            rows = self.rows.get(table)
            if rows is None or column not in self.fields.get(table, []):
                continue
            valid: Set[str] = set()
            for target in targets:
                valid |= self.ids.get(target, set())
            label = " or ".join(target[:-4] for target in targets)
            for row in rows:
                identifier = self.row_id(table, row)
                where = self.where(table, row, identifier)
                for reference in split_ids(row.get(column)):
                    if reference not in valid:
                        self.fail(
                            "{0} {1} references {2}, which is not in {3}".format(
                                where, column, reference, label
                            )
                        )

    def check_cycles(self) -> None:
        """Detect dependency cycles among calculations.

        Ported from add-fisheries-sector/scripts/validate_provenance.py:316-334,
        which the build-clews-model validator never had.
        """
        dependencies = {
            row.get("calculation_id", ""): split_ids(row.get("input_calculation_ids"))
            for row in self.rows.get("CALCULATIONS.csv", [])
            if row.get("calculation_id", "")
        }
        visiting: Set[str] = set()
        visited: Set[str] = set()
        reported: Set[frozenset] = set()

        def detect(calculation_id: str, chain: List[str]) -> None:
            if calculation_id in visiting:
                start = chain.index(calculation_id) if calculation_id in chain else 0
                cycle = chain[start:] + [calculation_id]
                signature = frozenset(cycle)
                if signature not in reported:
                    reported.add(signature)
                    self.fail(
                        "CALCULATIONS.csv: dependency cycle: " + " -> ".join(cycle)
                    )
                return
            if calculation_id in visited:
                return
            visiting.add(calculation_id)
            for dependency in dependencies.get(calculation_id, []):
                if dependency in dependencies:
                    detect(dependency, chain + [calculation_id])
            visiting.discard(calculation_id)
            visited.add(calculation_id)

        for calculation_id in sorted(dependencies):
            detect(calculation_id, [])

    def check_orphans(self) -> None:
        """Warn about ledger rows nothing in the model relies on."""
        active_calculations: Set[str] = set()
        active_assumptions: Set[str] = set()
        active_sources: Set[str] = set()
        for row in self.rows.get("MODEL_MAP.csv", []):
            for reference in split_ids(row.get("evidence_ids")):
                if reference in self.ids.get("CALCULATIONS.csv", set()):
                    active_calculations.add(reference)
                elif reference in self.ids.get("ASSUMPTIONS.csv", set()):
                    active_assumptions.add(reference)
                elif reference in self.ids.get("SOURCES.csv", set()):
                    active_sources.add(reference)

        calculation_rows = {
            row.get("calculation_id", ""): row
            for row in self.rows.get("CALCULATIONS.csv", [])
        }
        pending = list(active_calculations)
        while pending:
            row = calculation_rows.get(pending.pop())
            if row is None:
                continue
            active_sources.update(split_ids(row.get("source_ids")))
            active_assumptions.update(split_ids(row.get("assumption_ids")))
            for reference in split_ids(row.get("input_calculation_ids")):
                if reference not in active_calculations:
                    active_calculations.add(reference)
                    pending.append(reference)
        for assumption_id in sorted(active_assumptions):
            for row in self.rows.get("ASSUMPTIONS.csv", []):
                if row.get("assumption_id", "") == assumption_id:
                    active_sources.update(split_ids(row.get("evidence_source_ids")))

        for table, active in (
            ("SOURCES.csv", active_sources),
            ("CALCULATIONS.csv", active_calculations),
            ("ASSUMPTIONS.csv", active_assumptions),
        ):
            column = ID_COLUMN[table]
            for row in self.rows.get(table, []):
                identifier = row.get(column, "")
                if identifier and identifier not in active:
                    self.warn(
                        "{0} no MODEL_MAP row depends on this record".format(
                            self.where(table, row, identifier)
                        )
                    )

    # ------------------------------------------------ stage 4: input coverage

    def check_coverage(self) -> None:
        inputs_dir = self.model_inputs
        if inputs_dir is None:
            if self.stage == "delivery":
                self.fail(
                    "--model-inputs is required at --stage delivery so input "
                    "coverage can be proven"
                )
            return
        if not inputs_dir.is_dir():
            self.fail("model inputs directory does not exist: {0}".format(inputs_dir))
            return

        populated = [
            path.relative_to(inputs_dir).as_posix()
            for path in sorted(inputs_dir.rglob("*.csv"))
            if populated_csv(path)
        ]
        active = [
            row
            for row in self.rows.get("MODEL_MAP.csv", [])
            if not row.get("superseded_by", "")
        ]
        mapped = [row.get("model_file", "") for row in active if row.get("model_file")]
        mapped_csv = [
            model_file
            for model_file in mapped
            if Path(model_file).suffix.lower() == ".csv"
        ]
        uncovered = [
            relative
            for relative in populated
            if not any(covers(model_file, relative) for model_file in mapped_csv)
        ]
        required_populated = {
            relative
            for relative in populated
            if any(covers(required, relative) for required in self.required_inputs)
        }
        for required in self.required_inputs:
            if not any(covers(required, relative) for relative in populated):
                self.fail(
                    "required touched input matches no populated model input: {0}".format(
                        required
                    )
                )
        uncovered_required = sorted(set(uncovered) & required_populated)
        legacy_uncovered = sorted(set(uncovered) - required_populated)
        unmatched = sorted(
            {
                model_file
                for model_file in mapped_csv
                if not any(covers(model_file, relative) for relative in populated)
            }
        )
        if not populated:
            self.fail(
                "no populated input CSV found under {0}".format(inputs_dir)
            )
        if uncovered_required:
            self.fail(
                "touched model inputs have no MODEL_MAP row: {0}".format(
                    ", ".join(uncovered_required)
                )
            )
        if legacy_uncovered:
            message = "inherited untouched model inputs have no MODEL_MAP row: {0}".format(
                ", ".join(legacy_uncovered)
            )
            if self.allow_inherited_coverage_gaps and self.stage != "delivery":
                self.warn(message)
            else:
                self.fail(message)
        for model_file in unmatched:
            self.warn(
                "MODEL_MAP.csv: model_file {0} matches no populated input under "
                "{1}".format(model_file, inputs_dir)
            )
        self.coverage = {
            "directory": str(inputs_dir),
            "populated_input_count": len(populated),
            "covered_input_count": len(populated) - len(uncovered),
            "uncovered_inputs": uncovered,
            "required_inputs": sorted(self.required_inputs),
            "uncovered_required_inputs": uncovered_required,
            "legacy_uncovered_inputs": legacy_uncovered,
        }

    # ------------------------------------------------------------------ drive

    def run(self) -> Dict[str, object]:
        self.load()
        if self.stage != "scaffold" and self.rows:
            self.check_identifiers()
            self.check_required_values()
            self.check_sources()
            self.check_calculations()
            self.check_assumptions()
            self.check_model_map()
            self.check_references()
            self.check_cycles()
            self.check_changes()
            self.check_orphans()
            for table in ("SOURCES.csv", "MODEL_MAP.csv"):
                if table in self.rows and not self.rows[table]:
                    self.fail("{0} has no data rows".format(table))
            self.check_coverage()
        return self.report()

    def report(self) -> Dict[str, object]:
        report: Dict[str, object] = {
            "ledger_dir": str(self.ledger_dir),
            "stage": self.stage,
            "status": "fail" if self.failures else "pass",
            "failure_count": len(self.failures),
            "warning_count": len(self.warnings),
            "row_counts": {
                table: len(self.rows.get(table, [])) for table in LEDGER_TABLES
            },
            "verified_digests": self.verified_digests,
            "derived_evidence_types": self.evidence_types,
            "failures": self.failures,
            "warnings": self.warnings,
        }
        if self.coverage:
            report["model_inputs"] = self.coverage
        return report


def covers(model_file: str, relative_input: str) -> bool:
    """True when a MODEL_MAP.model_file names the given input file.

    Matching is on the file, never on a glob: an exact relative match, a path
    suffix match, or an equal basename.
    """
    candidate = model_file.strip().replace("\\", "/").lstrip("./")
    if not candidate or any(char in candidate for char in GLOB_CHARS):
        return False
    if candidate == relative_input:
        return True
    if relative_input.endswith("/" + candidate):
        return True
    return candidate.rsplit("/", 1)[-1] == relative_input.rsplit("/", 1)[-1]


def validate(
    ledger_dir: Path,
    stage: str = "build",
    model_inputs: Optional[Path] = None,
    required_inputs: Optional[Sequence[str]] = None,
    allow_inherited_coverage_gaps: bool = False,
) -> Dict[str, object]:
    validator = LedgerValidator(
        Path(ledger_dir).expanduser(),
        stage,
        Path(model_inputs).expanduser() if model_inputs else None,
        required_inputs,
        allow_inherited_coverage_gaps,
    )
    return validator.run()


def render(report: Dict[str, object]) -> str:
    lines = [
        "provenance: {0}  (stage={1}, ledger={2})".format(
            str(report["status"]).upper(), report["stage"], report["ledger_dir"]
        )
    ]
    counts = report.get("row_counts", {})
    if counts:
        lines.append(
            "  rows: "
            + ", ".join(
                "{0} {1}".format(table.replace(".csv", ""), count)
                for table, count in counts.items()
            )
        )
    lines.append("  evidence digests verified: {0}".format(report["verified_digests"]))
    inputs = report.get("model_inputs")
    if isinstance(inputs, dict):
        lines.append(
            "  model inputs covered: {0}/{1}".format(
                inputs.get("covered_input_count"), inputs.get("populated_input_count")
            )
        )
    for label, key in (("FAILURES", "failures"), ("WARNINGS", "warnings")):
        items = report.get(key) or []
        if items:
            lines.append("{0} ({1})".format(label, len(items)))
            lines.extend("  - {0}".format(item) for item in items)
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a six-table CLEWs provenance ledger."
    )
    parser.add_argument("ledger_dir", type=Path, help="directory holding the six CSVs")
    parser.add_argument("--stage", choices=STAGES, default="build")
    parser.add_argument(
        "--model-inputs",
        type=Path,
        help="directory of model input CSVs to check for MODEL_MAP coverage",
    )
    parser.add_argument(
        "--required-input",
        action="append",
        default=[],
        help="populated input file in the touched calibration scope; repeat as needed",
    )
    parser.add_argument(
        "--allow-inherited-coverage-gaps",
        action="store_true",
        help="warn on uncovered inherited untouched inputs before delivery",
    )
    parser.add_argument("--json", dest="json_path", type=Path, help="write a JSON report")
    args = parser.parse_args(argv)

    report = validate(
        args.ledger_dir,
        args.stage,
        args.model_inputs,
        args.required_input,
        args.allow_inherited_coverage_gaps,
    )
    print(render(report))
    if args.json_path:
        destination = args.json_path.expanduser()
        if destination.parent and str(destination.parent):
            destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 1 if report["failure_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
