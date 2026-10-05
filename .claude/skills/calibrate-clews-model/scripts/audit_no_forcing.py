#!/usr/bin/env python3
"""Audit a calibration wave for mechanical historical-forcing candidates."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


BOUND_PAIRS = (
    ("TMPAL", "TMPAU", "model_period_activity"),
    ("TAL", "TAU", "annual_activity"),
    ("TAMinC", "TAMaxC", "annual_capacity"),
    ("TAMinCI", "TAMaxCI", "annual_capacity_investment"),
)
PROHIBITED_SOLVE_TERMS = (
    "sensitivity",
    "sweep",
    "scenario ranking",
    "rank scenarios",
    "best fit",
    "best-fit",
    "a/b",
    "unchanged control",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def split_ids(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [item for item in re.split(r"[;,\s]+", value.strip()) if item]


def scan_parameters(case_dir: Path) -> dict[str, dict[str, list[dict[str, Any]]]]:
    parameters: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for path in sorted(case_dir.glob("*.json")):
        if path.name == "genData.json":
            continue
        payload = load_json(path)
        if not isinstance(payload, dict):
            continue
        for parameter, scenarios in payload.items():
            if not isinstance(scenarios, dict):
                continue
            parameters[parameter] = {
                str(scenario): [row for row in rows if isinstance(row, dict)]
                for scenario, rows in scenarios.items()
                if isinstance(rows, list)
            }
    return parameters


def years_for(case_dir: Path, parameters: dict[str, Any]) -> list[str]:
    gen_path = case_dir / "genData.json"
    if gen_path.is_file():
        gen = load_json(gen_path)
        if isinstance(gen, dict) and isinstance(gen.get("osy-years"), list):
            return [str(year) for year in gen["osy-years"]]
    discovered: set[str] = set()
    for scenarios in parameters.values():
        for rows in scenarios.values():
            for row in rows:
                discovered.update(
                    key
                    for key, value in row.items()
                    if isinstance(value, (int, float)) and str(key).isdigit()
                )
    return sorted(discovered)


def expanded(
    scenarios: dict[str, list[dict[str, Any]]], years: list[str]
) -> dict[str, dict[tuple[tuple[tuple[str, str], ...], str], float]]:
    result: dict[str, dict[tuple[tuple[tuple[str, str], ...], str], float]] = {}
    year_set = set(years)
    for scenario, rows in scenarios.items():
        indexed: dict[tuple[tuple[tuple[str, str], ...], str], float] = {}
        for row in rows:
            identity = tuple(
                sorted(
                    (str(key), str(value))
                    for key, value in row.items()
                    if key not in year_set and value is not None
                )
            )
            for year in years:
                value = row.get(year)
                if isinstance(value, (int, float)):
                    indexed[(identity, year)] = float(value)
        result[scenario] = indexed
    return result


def identity_token(identity: tuple[tuple[str, str], ...]) -> str:
    return ",".join(f"{key}={value}" for key, value in identity) or "global"


def bound_candidates(parameters: dict[str, Any], years: list[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for lower_name, upper_name, kind in BOUND_PAIRS:
        lower = expanded(parameters.get(lower_name, {}), years)
        upper = expanded(parameters.get(upper_name, {}), years)
        for scenario in sorted(set(lower) & set(upper)):
            for key in sorted(set(lower[scenario]) & set(upper[scenario])):
                low, high = lower[scenario][key], upper[scenario][key]
                if low <= 0:
                    continue
                if abs(low - high) <= max(1e-9, 1e-9 * max(abs(low), abs(high))):
                    identity, year = key
                    candidates.append(
                        {
                            "candidate_id": (
                                f"positive_bound_pair:{lower_name}:{upper_name}:"
                                f"{scenario}:{identity_token(identity)}:{year}"
                            ),
                            "candidate_type": "positive_bound_pair",
                            "kind": kind,
                            "lower_parameter": lower_name,
                            "upper_parameter": upper_name,
                            "scenario": scenario,
                            "identity": dict(identity),
                            "year": year,
                            "value": low,
                        }
                    )
        for scenario, values in sorted(upper.items()):
            for (identity, year), value in sorted(values.items()):
                if value == 0:
                    candidates.append(
                        {
                            "candidate_id": (
                                f"zero_upper_bound:{upper_name}:{scenario}:"
                                f"{identity_token(identity)}:{year}"
                            ),
                            "candidate_type": "zero_upper_bound",
                            "kind": kind,
                            "upper_parameter": upper_name,
                            "scenario": scenario,
                            "identity": dict(identity),
                            "year": year,
                            "value": 0.0,
                        }
                    )
    return candidates


def read_ledger(ledger_dir: Path) -> dict[str, dict[str, dict[str, str]]]:
    specifications = {
        "SOURCES.csv": "source_id",
        "CALCULATIONS.csv": "calculation_id",
        "ASSUMPTIONS.csv": "assumption_id",
    }
    result: dict[str, dict[str, dict[str, str]]] = {}
    for filename, key in specifications.items():
        with (ledger_dir / filename).open(newline="", encoding="utf-8-sig") as stream:
            result[filename] = {
                row[key].strip(): row
                for row in csv.DictReader(stream)
                if row.get(key, "").strip()
            }
    return result


def source_lineage(
    evidence_ids: list[str], ledger: dict[str, dict[str, dict[str, str]]]
) -> set[str]:
    pending, seen, sources = list(evidence_ids), set(), set()
    while pending:
        identifier = pending.pop()
        if identifier in seen:
            continue
        seen.add(identifier)
        if identifier in ledger["SOURCES.csv"]:
            sources.add(identifier)
        elif identifier in ledger["CALCULATIONS.csv"]:
            row = ledger["CALCULATIONS.csv"][identifier]
            for field in ("source_ids", "assumption_ids", "input_calculation_ids"):
                pending.extend(split_ids(row.get(field)))
        elif identifier in ledger["ASSUMPTIONS.csv"]:
            pending.extend(
                split_ids(
                    ledger["ASSUMPTIONS.csv"][identifier].get("evidence_source_ids")
                )
            )
    return sources


def benchmark_overlap_failures(
    package: dict[str, Any], ledger: dict[str, dict[str, dict[str, str]]]
) -> list[dict[str, str]]:
    benchmark_sources = {
        source_id
        for benchmark in package.get("benchmarks", [])
        if isinstance(benchmark, dict)
        for source_id in benchmark.get("source_ids", [])
        if isinstance(source_id, str)
    }
    failures: list[dict[str, str]] = []
    for change in package.get("changes", []):
        if not isinstance(change, dict):
            continue
        exceptions = {
            item.get("source_id")
            for item in change.get("benchmark_source_exceptions", [])
            if isinstance(item, dict)
            and isinstance(item.get("source_id"), str)
            and isinstance(item.get("reason"), str)
            and item["reason"].strip()
        }
        overlap = source_lineage(change.get("evidence_ids", []), ledger) & benchmark_sources
        for source_id in sorted(overlap - exceptions):
            failures.append(
                {
                    "change_id": str(change.get("change_id", "")),
                    "source_id": source_id,
                    "reason": "diagnostic benchmark enters parameter evidence lineage",
                }
            )
    return failures


def audit(
    case_dir: Path, package: dict[str, Any], ledger_dir: Path
) -> dict[str, Any]:
    parameters = scan_parameters(case_dir)
    years = years_for(case_dir, parameters)
    candidates = bound_candidates(parameters, years)
    ledger = read_ledger(ledger_dir)
    overlap_failures = benchmark_overlap_failures(package, ledger)

    dispositions = {
        item.get("candidate_id"): item
        for item in package.get("non_forcing", {}).get("candidate_dispositions", [])
        if isinstance(item, dict) and isinstance(item.get("candidate_id"), str)
    }
    candidate_ids = {item["candidate_id"] for item in candidates}
    unresolved: list[str] = []
    invalid_dispositions: list[str] = []
    ledger_evidence_ids = set().union(
        ledger["SOURCES.csv"],
        ledger["CALCULATIONS.csv"],
        ledger["ASSUMPTIONS.csv"],
    )
    for candidate_id in sorted(candidate_ids):
        disposition = dispositions.get(candidate_id)
        evidence_ids = disposition.get("evidence_ids", []) if disposition else []
        valid_evidence = (
            isinstance(evidence_ids, list)
            and bool(evidence_ids)
            and all(
                isinstance(identifier, str) and identifier in ledger_evidence_ids
                for identifier in evidence_ids
            )
        )
        valid_reason = bool(
            disposition
            and isinstance(disposition.get("reason"), str)
            and disposition["reason"].strip()
        )
        if (
            not disposition
            or disposition.get("status") != "allowed_physical_input"
            or not valid_evidence
            or not valid_reason
        ):
            unresolved.append(candidate_id)
            if disposition:
                invalid_dispositions.append(candidate_id)
    stale_allowed = sorted(
        candidate_id
        for candidate_id, disposition in dispositions.items()
        if candidate_id not in candidate_ids
        and disposition.get("status") == "allowed_physical_input"
    )
    unresolved.extend(stale_allowed)

    prohibited_attempts: list[dict[str, Any]] = []
    for index, attempt in enumerate(package.get("runtime", {}).get("solve_attempts", [])):
        if not isinstance(attempt, dict):
            continue
        purpose = str(attempt.get("purpose", ""))
        lowered = purpose.lower()
        if any(term in lowered for term in PROHIBITED_SOLVE_TERMS):
            prohibited_attempts.append({"index": index, "purpose": purpose})

    status = (
        "fail"
        if unresolved or invalid_dispositions or overlap_failures or prohibited_attempts
        else "pass"
    )
    return {
        "schema": "clews-non-forcing-audit-v1",
        "status": status,
        "case_dir": str(case_dir.resolve()),
        "ledger_dir": str(ledger_dir.resolve()),
        "years": years,
        "candidates": candidates,
        "unresolved_candidates": unresolved,
        "invalid_dispositions": invalid_dispositions,
        "benchmark_lineage_failures": overlap_failures,
        "prohibited_solve_attempts": prohibited_attempts,
        "interpretation": (
            "Mechanical candidates require sourced physical-input dispositions. "
            "Benchmark lineage and calibration sweeps are not waivable."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--ledger-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        package = load_json(args.package)
        if not isinstance(package, dict):
            raise TypeError("package root must be an object")
        report = audit(
            args.case_dir.expanduser().resolve(),
            package,
            args.ledger_dir.expanduser().resolve(),
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
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
