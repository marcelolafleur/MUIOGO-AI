#!/usr/bin/env python3
"""Validate arithmetic and semantics of a closed CLEWs resource account."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any


ROLES = {"fixed", "protected", "flexible", "residual", "disabled", "stock", "flow"}
ANNUAL_IMPLEMENTATIONS = {"adjacent_year_net_constraint", "gross_flow_constraint"}


def number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def text_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(v, str) and v.strip() for v in value)
    )


def read_ledger_ids(ledger_dir: Path) -> dict[str, set[str]]:
    specifications = {
        "sources": ("SOURCES.csv", "source_id"),
        "calculations": ("CALCULATIONS.csv", "calculation_id"),
        "assumptions": ("ASSUMPTIONS.csv", "assumption_id"),
    }
    result: dict[str, set[str]] = {}
    for name, (filename, column) in specifications.items():
        with (ledger_dir / filename).open(newline="", encoding="utf-8-sig") as stream:
            result[name] = {
                row.get(column, "").strip()
                for row in csv.DictReader(stream)
                if row.get(column, "").strip()
            }
    return result


def validate_account(
    account: Any, ledger_ids: dict[str, set[str]] | None = None
) -> list[str]:
    errors: list[str] = []
    if not isinstance(account, dict):
        return ["account root must be an object"]
    if account.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    for field in ("account_id", "unit", "base_year"):
        if not isinstance(account.get(field), str) or not account[field].strip():
            errors.append(f"{field} must be non-empty text")
    years = account.get("years")
    if not text_list(years):
        errors.append("years must be a non-empty list of text")
        years = []
    if len(set(years)) != len(years):
        errors.append("years contains duplicates")
    base_year = account.get("base_year")
    if base_year not in years:
        errors.append("base_year must appear in years")
    totals = account.get("total")
    if not isinstance(totals, dict) or any(
        not number(totals.get(year)) for year in years
    ):
        errors.append("total must contain a finite number for every year")
        totals = {}

    reconciliation = account.get("boundary_reconciliation")
    if not isinstance(reconciliation, dict):
        errors.append("boundary_reconciliation must be an object")
    else:
        required_numbers = (
            "published_total",
            "excluded_total",
            "mapped_source_total",
            "model_control_total",
            "tolerance",
        )
        for field in required_numbers:
            if not number(reconciliation.get(field)):
                errors.append(f"boundary_reconciliation.{field} must be finite")
        if all(number(reconciliation.get(field)) for field in required_numbers):
            tolerance = reconciliation["tolerance"]
            expected = (
                reconciliation["published_total"] - reconciliation["excluded_total"]
            )
            if abs(expected - reconciliation["mapped_source_total"]) > tolerance:
                errors.append("boundary reconciliation does not close after exclusions")
            if (
                years
                and abs(
                    reconciliation["model_control_total"]
                    - totals.get(base_year, math.inf)
                )
                > tolerance
            ):
                errors.append(
                    "model_control_total does not equal base-year account total"
                )
        calculation_ids = reconciliation.get("calculation_ids")
        if not text_list(calculation_ids):
            errors.append("boundary_reconciliation.calculation_ids must be non-empty")
        elif ledger_ids is not None:
            for identifier in calculation_ids:
                if identifier not in ledger_ids["calculations"]:
                    errors.append(
                        "boundary_reconciliation.calculation_ids does not resolve: "
                        f"{identifier}"
                    )

    classes = account.get("classes")
    if not isinstance(classes, list) or not classes:
        errors.append("classes must be a non-empty list")
        classes = []
    class_ids: set[str] = set()
    lower_sums = {year: 0.0 for year in years}
    upper_sums = {year: 0.0 for year in years}
    base_sum = 0.0
    for index, item in enumerate(classes):
        location = f"classes[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location} must be an object")
            continue
        class_id = item.get("class_id")
        if not isinstance(class_id, str) or not class_id.strip():
            errors.append(f"{location}.class_id must be non-empty text")
            continue
        if class_id in class_ids:
            errors.append(f"{location}.class_id duplicates {class_id}")
        class_ids.add(class_id)
        if item.get("role") not in ROLES:
            errors.append(f"{location}.role must be one of {sorted(ROLES)}")
        base = item.get("base_year_value")
        if not number(base):
            errors.append(f"{location}.base_year_value must be finite")
            base = 0.0
        base_sum += float(base)
        lower, upper = item.get("lower"), item.get("upper")
        if not isinstance(lower, dict) or not isinstance(upper, dict):
            errors.append(f"{location}.lower and upper must be objects")
            continue
        for year in years:
            lo, hi = lower.get(year), upper.get(year)
            if not number(lo) or not number(hi):
                errors.append(f"{location} lacks finite bounds for {year}")
                continue
            if lo > hi:
                errors.append(f"{location} lower exceeds upper in {year}")
            lower_sums[year] += float(lo)
            upper_sums[year] += float(hi)
        if (
            base_year in years
            and number(lower.get(base_year))
            and number(upper.get(base_year))
        ):
            if (
                abs(lower[base_year] - base) > 1e-9
                or abs(upper[base_year] - base) > 1e-9
            ):
                errors.append(
                    f"{location} base year is not initialized by lower/upper equality"
                )
        if item.get("role") == "residual" and any(
            number(upper.get(year)) and upper[year] >= 99990 for year in years
        ):
            errors.append(
                f"{location} residual route has an effectively unbounded upper limit"
            )
        evidence_ids = item.get("evidence_ids")
        if not text_list(evidence_ids):
            errors.append(f"{location}.evidence_ids must be non-empty")
        elif ledger_ids is not None:
            allowed = set().union(*ledger_ids.values())
            for identifier in evidence_ids:
                if identifier not in allowed:
                    errors.append(f"{location}.evidence_ids does not resolve: {identifier}")

    if base_year in totals and abs(base_sum - totals[base_year]) > 1e-9:
        errors.append("base-year class values do not close to the account total")
    for year in years:
        if year not in totals:
            continue
        if lower_sums[year] > totals[year] + 1e-9:
            errors.append(f"sum of class floors exceeds total in {year}")
        if upper_sums[year] < totals[year] - 1e-9:
            errors.append(f"sum of class ceilings is below total in {year}")

    transitions = account.get("transitions")
    if not isinstance(transitions, list):
        errors.append("transitions must be a list")
        transitions = []
    for index, item in enumerate(transitions):
        location = f"transitions[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location} must be an object")
            continue
        for field in ("transition_id", "claim", "implementation", "unit"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{location}.{field} must be non-empty text")
        if not number(item.get("rate")) or item.get("rate", -1) < 0:
            errors.append(f"{location}.rate must be a nonnegative finite number")
        for field in ("source_class_ids", "destination_class_ids"):
            values = item.get(field)
            if not text_list(values):
                errors.append(f"{location}.{field} must be non-empty")
            elif set(values) - class_ids:
                errors.append(f"{location}.{field} contains unknown classes")
        if (
            item.get("claim") == "annual_maximum"
            and item.get("implementation") not in ANNUAL_IMPLEMENTATIONS
        ):
            errors.append(
                f"{location} claims an annual maximum without an adjacent-year or gross-flow constraint"
            )
        evidence_ids = item.get("evidence_ids")
        if not text_list(evidence_ids):
            errors.append(f"{location}.evidence_ids must be non-empty")
        elif ledger_ids is not None:
            allowed = set().union(*ledger_ids.values())
            for identifier in evidence_ids:
                if identifier not in allowed:
                    errors.append(f"{location}.evidence_ids does not resolve: {identifier}")

    scope = account.get("index_scope")
    if not isinstance(scope, dict):
        errors.append("index_scope must be an object")
    else:
        for field in ("account_scope", "constraint_scope"):
            if not isinstance(scope.get(field), str) or not scope[field].strip():
                errors.append(f"index_scope.{field} must be non-empty text")
        allocation = scope.get("allocation_evidence_ids")
        if scope.get("account_scope") != scope.get(
            "constraint_scope"
        ) and not text_list(allocation):
            errors.append(
                "different account and constraint scopes require allocation_evidence_ids"
            )
        if text_list(allocation) and ledger_ids is not None:
            allowed = set().union(*ledger_ids.values())
            for identifier in allocation:
                if identifier not in allowed:
                    errors.append(
                        "index_scope.allocation_evidence_ids does not resolve: "
                        f"{identifier}"
                    )

    export = account.get("export_checks")
    check = export.get("zero_and_sentinel_bounds") if isinstance(export, dict) else None
    if (
        not isinstance(check, dict)
        or check.get("status") != "passed"
        or not isinstance(check.get("artifact"), str)
        or not check["artifact"].strip()
    ):
        errors.append(
            "export_checks.zero_and_sentinel_bounds must be passed with an artifact"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("account", type=Path)
    parser.add_argument("--ledger-dir", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    try:
        account = json.loads(args.account.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    try:
        ledger_ids = read_ledger_ids(args.ledger_dir) if args.ledger_dir else None
    except OSError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    errors = validate_account(account, ledger_ids)
    report = {
        "schema": "clews-resource-account-validation-v1",
        "status": "fail" if errors else "pass",
        "account": str(args.account.resolve()),
        "ledger_dir": str(args.ledger_dir.resolve()) if args.ledger_dir else None,
        "account_id": account.get("account_id") if isinstance(account, dict) else None,
        "errors": errors,
    }
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        print("resource account: FAIL", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("resource account: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
