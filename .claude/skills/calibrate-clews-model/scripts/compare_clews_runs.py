#!/usr/bin/env python3
"""Compare two CLEWs CSV result directories at row and structural levels."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


CORE_FILES = {
    "AccumulatedNewCapacity.csv",
    "AnnualFixedOperatingCost.csv",
    "AnnualVariableOperatingCost.csv",
    "AnnualizedInvestmentCost.csv",
    "CapitalInvestment.csv",
    "Demand.csv",
    "E8_AnnualEmissionsLimit.csv",
    "NewCapacity.csv",
    "ObjectiveValue.csv",
    "SalvageValue.csv",
    "TechnologyEmissionsPenalty.csv",
    "TotalCapacityAnnual.csv",
    "UDC1_UserDefinedConstraintInequality.csv",
}
EXACT_PARITY = "EXACT_PARITY"
ALTERNATE_OPTIMUM = "STRUCTURAL_PARITY_ALTERNATE_OPTIMUM_CANDIDATE"
MATERIAL_CHANGE = "MATERIAL_CHANGE"
DIMENSION_NAMES = {
    "t": "technologies",
    "y": "years",
    "f": "commodities",
    "e": "emissions",
}


def load_rules(path: Path | None) -> tuple[set[str], dict[str, dict[str, str]]]:
    if path is None:
        return set(), {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object")
    retired = raw.get("retired_values", [])
    groups = raw.get("equivalence_groups", {})
    if not isinstance(retired, list) or not all(
        isinstance(value, str) for value in retired
    ):
        raise ValueError("rules.retired_values must be a list of exact identifiers")
    if not isinstance(groups, dict):
        raise ValueError("rules.equivalence_groups must be an object")
    lookup: dict[str, dict[str, str]] = {}
    for dimension, named_groups in groups.items():
        if not isinstance(dimension, str) or not isinstance(named_groups, dict):
            raise ValueError(
                "each equivalence_groups dimension must contain named groups"
            )
        lookup[dimension] = {}
        for group, members in named_groups.items():
            if (
                not isinstance(group, str)
                or not isinstance(members, list)
                or not all(isinstance(member, str) for member in members)
            ):
                raise ValueError(
                    "equivalence groups must map names to identifier lists"
                )
            for member in members:
                if member in lookup[dimension]:
                    raise ValueError(
                        f"equivalence identifier appears twice: {dimension}={member}"
                    )
                lookup[dimension][member] = group
    return set(retired), lookup


def table(
    path: Path,
    retired_values: set[str],
    equivalence_groups: dict[str, dict[str, str]],
) -> tuple[
    list[str], str, dict[tuple[str, ...], float], dict[tuple[str, ...], float], int
]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) < 2:
            raise ValueError(f"{path} has no usable header")
        keys, value = reader.fieldnames[:-1], reader.fieldnames[-1]
        raw: dict[tuple[str, ...], float] = defaultdict(float)
        aggregate: dict[tuple[str, ...], float] = defaultdict(float)
        filtered = 0
        for line, row in enumerate(reader, start=2):
            coordinates = tuple(row[key] for key in keys)
            if any(coordinate in retired_values for coordinate in coordinates):
                filtered += 1
                continue
            try:
                number = float(row[value])
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path}:{line} {value} is not numeric") from error
            raw[coordinates] += number
            grouped = tuple(
                equivalence_groups.get(key, {}).get(coordinate, coordinate)
                for key, coordinate in zip(keys, coordinates)
            )
            aggregate[grouped] += number
    return keys, value, dict(raw), dict(aggregate), filtered


def changed_keys(
    before: dict[tuple[str, ...], float],
    after: dict[tuple[str, ...], float],
    tolerance: float,
) -> list[tuple[str, ...]]:
    return [
        key
        for key in set(before) | set(after)
        if abs(after.get(key, 0.0) - before.get(key, 0.0)) > tolerance
    ]


def affected_dimensions(
    keys: list[str], changed: list[tuple[str, ...]]
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for index, key in enumerate(keys):
        if key in DIMENSION_NAMES:
            result[DIMENSION_NAMES[key]] = sorted({row[index] for row in changed})
    return result


def compare(
    baseline: Path,
    candidate: Path,
    tolerance: float,
    structural_files: set[str] | None = None,
    retired_values: set[str] | None = None,
    equivalence_groups: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    structural_files = CORE_FILES if structural_files is None else structural_files
    retired_values = set() if retired_values is None else retired_values
    equivalence_groups = {} if equivalence_groups is None else equivalence_groups
    baseline_files = {path.name for path in baseline.glob("*.csv")}
    candidate_files = {path.name for path in candidate.glob("*.csv")}
    if not baseline_files:
        raise ValueError(f"{baseline} contains no CSV result tables")
    if not candidate_files:
        raise ValueError(f"{candidate} contains no CSV result tables")
    common = sorted(baseline_files & candidate_files)
    baseline_only = sorted(baseline_files - candidate_files)
    candidate_only = sorted(candidate_files - baseline_files)
    reports: list[dict[str, Any]] = []
    affected: dict[str, set[str]] = {name: set() for name in DIMENSION_NAMES.values()}
    for name in common:
        bkeys, bvalue, before, before_aggregate, bfiltered = table(
            baseline / name, retired_values, equivalence_groups
        )
        ckeys, cvalue, after, after_aggregate, cfiltered = table(
            candidate / name, retired_values, equivalence_groups
        )
        if bkeys != ckeys or bvalue != cvalue:
            reports.append({"file": name, "status": "schema_mismatch"})
            continue
        raw_changed = changed_keys(before, after, tolerance)
        aggregate_changed = changed_keys(before_aggregate, after_aggregate, tolerance)
        dimensions = affected_dimensions(bkeys, raw_changed)
        for dimension, values in dimensions.items():
            affected[dimension].update(values)
        total_before, total_after = sum(before.values()), sum(after.values())
        percent = (
            None
            if total_before == 0
            else (total_after - total_before) / abs(total_before) * 100
        )
        reports.append(
            {
                "file": name,
                "status": "changed" if raw_changed else "unchanged",
                "aggregate_status": "changed" if aggregate_changed else "unchanged",
                "structural_priority": name in structural_files,
                "key_columns": bkeys,
                "value_column": bvalue,
                "baseline_total": total_before,
                "candidate_total": total_after,
                "total_change": total_after - total_before,
                "percent_change": percent,
                "changed_rows": len(raw_changed),
                "changed_aggregate_rows": len(aggregate_changed),
                "maximum_absolute_row_change": max(
                    (
                        abs(after.get(key, 0.0) - before.get(key, 0.0))
                        for key in raw_changed
                    ),
                    default=0.0,
                ),
                "maximum_absolute_aggregate_change": max(
                    (
                        abs(
                            after_aggregate.get(key, 0.0)
                            - before_aggregate.get(key, 0.0)
                        )
                        for key in aggregate_changed
                    ),
                    default=0.0,
                ),
                "filtered_rows": {"baseline": bfiltered, "candidate": cfiltered},
                "affected": dimensions,
            }
        )
    structural = [item for item in reports if item.get("structural_priority")]
    structural_summary = {
        item["file"]: (
            "schema_mismatch"
            if item["status"] == "schema_mismatch"
            else item["aggregate_status"]
        )
        for item in structural
    }
    for name in baseline_only:
        if name in structural_files:
            structural_summary[name] = "baseline_only"
    for name in candidate_only:
        if name in structural_files:
            structural_summary[name] = "candidate_only"
    same_files = not baseline_only and not candidate_only
    schema_match = all(item["status"] != "schema_mismatch" for item in reports)
    strict_parity = (
        same_files
        and schema_match
        and all(item["status"] == "unchanged" for item in reports)
    )
    structural_parity = (
        same_files
        and schema_match
        and all(item["aggregate_status"] == "unchanged" for item in structural)
    )
    if strict_parity:
        classification = EXACT_PARITY
    elif structural_parity:
        classification = ALTERNATE_OPTIMUM
    else:
        classification = MATERIAL_CHANGE
    return {
        "schema": "clews-run-comparison-v2",
        "status": "pass" if schema_match else "fail",
        "classification": classification,
        "strict_row_parity": strict_parity,
        "structural_parity": structural_parity,
        "alternative_optimum_candidate": classification == ALTERNATE_OPTIMUM,
        "baseline": str(baseline.resolve()),
        "candidate": str(candidate.resolve()),
        "tolerance": tolerance,
        "common_file_count": len(common),
        "baseline_only": baseline_only,
        "candidate_only": candidate_only,
        "structural_files": sorted(structural_files),
        "structural_summary": structural_summary,
        "affected": {key: sorted(values) for key, values in affected.items()},
        "rules": {
            "retired_values": sorted(retired_values),
            "equivalence_groups": equivalence_groups,
        },
        "files": reports,
        "interpretation": "Classification is diagnostic. Promote an alternate-optimum candidate only after recording an explicit acceptance decision.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_csv_dir", type=Path)
    parser.add_argument("candidate_csv_dir", type=Path)
    parser.add_argument("--tolerance", type=float, default=1e-7)
    parser.add_argument(
        "--structural",
        action="append",
        metavar="CSV",
        help="core structural result table; repeat to replace the defaults",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        help="JSON with exact retired_values and optional equivalence_groups by dimension",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.tolerance) or args.tolerance < 0:
        print("FAIL: tolerance must be finite and nonnegative", file=sys.stderr)
        return 2
    try:
        structural = set(args.structural) if args.structural else None
        retired, groups = load_rules(args.rules)
        report = compare(
            args.baseline_csv_dir,
            args.candidate_csv_dir,
            args.tolerance,
            structural,
            retired,
            groups,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
