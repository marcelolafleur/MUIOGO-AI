#!/usr/bin/env python3
"""Audit MUIO technology/commodity connectivity and unlimited-free candidates."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROLE_INPUT_EXEMPT = {"resource_supply", "accounting", "environmental_sink"}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_ledger_evidence_ids(ledger_dir: Path) -> set[str]:
    specifications = (
        ("SOURCES.csv", "source_id"),
        ("CALCULATIONS.csv", "calculation_id"),
        ("ASSUMPTIONS.csv", "assumption_id"),
    )
    identifiers: set[str] = set()
    for filename, column in specifications:
        with (ledger_dir / filename).open(newline="", encoding="utf-8-sig") as stream:
            identifiers.update(
                row.get(column, "").strip()
                for row in csv.DictReader(stream)
                if row.get(column, "").strip()
            )
    return identifiers


def rows(
    document: dict[str, Any], parameter: str, scenario: str
) -> list[dict[str, Any]]:
    value = document.get(parameter, {})
    if not isinstance(value, dict):
        return []
    selected = value.get(scenario, [])
    return selected if isinstance(selected, list) else []


def positive_years(row: dict[str, Any], years: list[str]) -> set[str]:
    return {
        year
        for year in years
        if isinstance(row.get(year), (int, float)) and row[year] > 0
    }


def numeric_values(row: dict[str, Any], years: list[str]) -> list[float]:
    return [
        float(row[year]) for year in years if isinstance(row.get(year), (int, float))
    ]


def row_index(
    source: list[dict[str, Any]], include_mode: bool = False
) -> dict[tuple[str, int | None], dict[str, Any]]:
    indexed: dict[tuple[str, int | None], dict[str, Any]] = {}
    for row in source:
        tech = row.get("TechId")
        if not isinstance(tech, str):
            continue
        mode = row.get("MoId") if include_mode else None
        indexed[(tech, mode)] = row
    return indexed


def all_nonpositive(row: dict[str, Any] | None, years: list[str]) -> bool:
    if row is None:
        return True
    values = numeric_values(row, years)
    return not values or max(values) <= 0


def finite_upper_years(
    row: dict[str, Any] | None, years: list[str], threshold: float
) -> set[str]:
    if row is None:
        return set()
    return {
        year
        for year in years
        if isinstance(row.get(year), (int, float)) and -1 < float(row[year]) < threshold
    }


def positive_cost_years(
    source: list[dict[str, Any] | None], years: list[str]
) -> set[str]:
    return {
        year
        for year in years
        if any(
            row is not None
            and isinstance(row.get(year), (int, float))
            and float(row[year]) > 0
            for row in source
        )
    }


def all_zero(row: dict[str, Any] | None, years: list[str]) -> bool:
    if row is None:
        return False
    values = numeric_values(row, years)
    return bool(values) and all(value == 0 for value in values)


def audit(
    case_dir: Path,
    rules: dict[str, Any],
    ledger_evidence_ids: set[str] | None = None,
) -> dict[str, Any]:
    gen = load(case_dir / "genData.json")
    rytcm = load(case_dir / "RYTCM.json")
    ryt = load(case_dir / "RYT.json")
    rytm = load(case_dir / "RYTM.json")
    scenario = str(
        rules.get("scenario")
        or next(
            (
                item.get("ScenarioId")
                for item in gen.get("osy-scenarios", [])
                if item.get("Active")
            ),
            "SC_0",
        )
    )
    years = [str(year) for year in gen.get("osy-years", [])]
    threshold = float(rules.get("unbounded_threshold", 99990))

    technologies = {
        item["TechId"]: item
        for item in gen.get("osy-tech", [])
        if isinstance(item, dict) and isinstance(item.get("TechId"), str)
    }
    commodities = {
        item["CommId"]: item
        for item in gen.get("osy-comm", [])
        if isinstance(item, dict) and isinstance(item.get("CommId"), str)
    }
    roles = rules.get("technology_roles", {})
    terminal = set(rules.get("terminal_commodity_ids", []))
    exogenous = set(rules.get("exogenous_commodity_ids", []))

    mode_inputs: dict[tuple[str, int], set[str]] = defaultdict(set)
    mode_outputs: dict[tuple[str, int], set[str]] = defaultdict(set)
    mode_input_years: dict[tuple[str, int], set[str]] = defaultdict(set)
    mode_output_years: dict[tuple[str, int], set[str]] = defaultdict(set)
    producers: dict[str, set[str]] = defaultdict(set)
    consumers: dict[str, set[str]] = defaultdict(set)
    for parameter, target, graph in (
        ("IAR", mode_inputs, consumers),
        ("OAR", mode_outputs, producers),
    ):
        for row in rows(rytcm, parameter, scenario):
            tech, commodity, mode = (
                row.get("TechId"),
                row.get("CommId"),
                row.get("MoId"),
            )
            if (
                not isinstance(tech, str)
                or not isinstance(commodity, str)
                or not isinstance(mode, int)
            ):
                continue
            active_years = positive_years(row, years)
            if active_years:
                target[(tech, mode)].add(commodity)
                graph[commodity].add(f"{tech}:{mode}")
                year_target = (
                    mode_input_years if parameter == "IAR" else mode_output_years
                )
                year_target[(tech, mode)].update(active_years)

    findings: list[dict[str, Any]] = []

    def add(
        kind: str,
        entity: str,
        severity: str,
        message: str,
        detail: Any,
        *,
        rule_id: str | None = None,
    ) -> None:
        identifier = f"{kind}:{entity}"
        if rule_id:
            identifier = f"{kind}:{rule_id}:{entity}"
        findings.append(
            {
                "finding_id": identifier,
                "finding_type": kind,
                "entity_id": entity,
                "severity": severity,
                "message": message,
                "detail": detail,
            }
        )

    for commodity, metadata in commodities.items():
        produced, consumed = (
            producers.get(commodity, set()),
            consumers.get(commodity, set()),
        )
        label = metadata.get("Comm", commodity)
        if produced and not consumed and commodity not in terminal:
            add(
                "commodity_without_consumer",
                commodity,
                "medium",
                f"{label} is produced but never consumed",
                sorted(produced),
            )
        if consumed and not produced and commodity not in exogenous:
            add(
                "commodity_without_producer",
                commodity,
                "high",
                f"{label} is consumed but has no modeled producer",
                sorted(consumed),
            )
        if not produced and not consumed and commodity not in terminal | exogenous:
            add(
                "unused_commodity",
                commodity,
                "low",
                f"{label} has no positive input or output ratio",
                {},
            )

    vc = row_index(rows(rytm, "VC", scenario), include_mode=True)
    tamul = row_index(rows(rytm, "TAMUL", scenario), include_mode=True)
    tau = row_index(rows(ryt, "TAU", scenario))
    cc = row_index(rows(ryt, "CC", scenario))
    fc = row_index(rows(ryt, "FC", scenario))
    tamaxc = row_index(rows(ryt, "TAMaxC", scenario))
    tamaxci = row_index(rows(ryt, "TAMaxCI", scenario))

    for key, outputs in sorted(mode_outputs.items()):
        tech, mode = key
        entity = f"{tech}:{mode}"
        role = (
            roles.get(tech, {}).get("role")
            if isinstance(roles.get(tech), dict)
            else None
        )
        active_years = mode_output_years.get(key, set())
        inputless_years = active_years - mode_input_years.get(key, set())
        if inputless_years and role not in ROLE_INPUT_EXEMPT:
            add(
                "inputless_output_mode",
                entity,
                "medium",
                "Mode has useful output without a positive modeled input in one or more years and no exempt declared role",
                {
                    "outputs": sorted(outputs),
                    "declared_role": role,
                    "inputless_years": sorted(inputless_years),
                },
            )
        bounded_years = set().union(
            finite_upper_years(tamul.get(key), years, threshold),
            finite_upper_years(tau.get((tech, None)), years, threshold),
            finite_upper_years(tamaxc.get((tech, None)), years, threshold),
            finite_upper_years(tamaxci.get((tech, None)), years, threshold),
        )
        costed_years = positive_cost_years(
            [vc.get(key), cc.get((tech, None)), fc.get((tech, None))], years
        )
        unbounded_years = active_years - bounded_years
        zero_cost_years = active_years - costed_years
        unlimited_free_years = inputless_years & unbounded_years & zero_cost_years
        if unlimited_free_years:
            add(
                "unlimited_free_output_candidate",
                entity,
                "high",
                "Inputless output mode has no positive modeled cost or finite activity/capacity upper bound in one or more years",
                {
                    "outputs": sorted(outputs),
                    "declared_role": role,
                    "threshold": threshold,
                    "unlimited_free_years": sorted(unlimited_free_years),
                    "unbounded_years": sorted(unbounded_years),
                    "zero_cost_years": sorted(zero_cost_years),
                    "inputless_years": sorted(inputless_years),
                },
            )
        if all_zero(tamul.get(key), years) or all_zero(tau.get((tech, None)), years):
            add(
                "zero_upper_requires_export_check",
                entity,
                "medium",
                "Source upper bound is zero; verify that the exporter preserves it as an active bound",
                {
                    "parameters": [
                        name
                        for name, row in (
                            ("TAMUL", tamul.get(key)),
                            ("TAU", tau.get((tech, None))),
                        )
                        if all_zero(row, years)
                    ]
                },
            )

    rule_errors: list[str] = []
    for tech in sorted(set(roles) - set(technologies)):
        rule_errors.append(f"technology_roles names unknown technology {tech}")
    for field, declared, known in (
        ("terminal_commodity_ids", terminal, set(commodities)),
        ("exogenous_commodity_ids", exogenous, set(commodities)),
    ):
        for commodity in sorted(declared - known):
            rule_errors.append(f"{field} names unknown commodity {commodity}")

    seen_rule_ids: set[str] = set()
    for index, item in enumerate(rules.get("required_links", [])):
        if not isinstance(item, dict):
            rule_errors.append(f"required_links[{index}] must be an object")
            continue
        rule_id = item.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            rule_errors.append(f"required_links[{index}].rule_id must be non-empty")
            continue
        if rule_id in seen_rule_ids:
            rule_errors.append(f"required_links rule_id duplicates {rule_id}")
        seen_rule_ids.add(rule_id)
        required_ids = item.get("required_input_commodity_ids", [])
        technology_ids = item.get("technology_ids", [])
        if not isinstance(required_ids, list) or not required_ids:
            rule_errors.append(
                f"required_links[{rule_id}].required_input_commodity_ids must be non-empty"
            )
            required_ids = []
        if not isinstance(technology_ids, list) or not technology_ids:
            rule_errors.append(
                f"required_links[{rule_id}].technology_ids must be non-empty"
            )
            technology_ids = []
        if not isinstance(item.get("require_all", True), bool):
            rule_errors.append(f"required_links[{rule_id}].require_all must be boolean")
        required = set(required_ids)
        unknown_commodities = required - set(commodities)
        for commodity in sorted(unknown_commodities):
            rule_errors.append(
                f"required_links[{rule_id}] names unknown commodity {commodity}"
            )
        require_all = item.get("require_all", True)
        for tech in technology_ids:
            if tech not in technologies:
                rule_errors.append(
                    f"required_links[{rule_id}] names unknown technology {tech}"
                )
                continue
            modes = sorted(key for key in mode_outputs if key[0] == tech)
            if not modes:
                rule_errors.append(
                    f"required_links[{rule_id}] technology {tech} has no positive output modes"
                )
            for key in modes:
                present = mode_inputs.get(key, set())
                satisfied = (
                    required <= present if require_all else bool(required & present)
                )
                if not satisfied:
                    entity = f"{key[0]}:{key[1]}"
                    add(
                        "required_link_missing",
                        entity,
                        "high",
                        str(
                            item.get("reason")
                            or "Declared physical input link is missing"
                        ),
                        {
                            "rule_id": rule_id,
                            "required": sorted(required),
                            "present": sorted(present),
                            "require_all": require_all,
                        },
                        rule_id=rule_id,
                    )

    exemption_keys: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(rules.get("reviewed_exemptions", [])):
        if not isinstance(item, dict):
            rule_errors.append(f"reviewed_exemptions[{index}] must be an object")
            continue
        finding_id = item.get("finding_id")
        if not isinstance(finding_id, str) or not finding_id.strip():
            rule_errors.append(
                f"reviewed_exemptions[{index}] must name the complete finding_id"
            )
            continue
        if finding_id in exemption_keys:
            rule_errors.append(f"reviewed_exemptions duplicates {finding_id}")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            rule_errors.append(f"reviewed_exemptions[{index}].reason must be non-empty")
        evidence_ids = item.get("evidence_ids")
        if (
            not isinstance(evidence_ids, list)
            or not evidence_ids
            or not all(
                isinstance(value, str) and value.strip() for value in evidence_ids
            )
        ):
            rule_errors.append(
                f"reviewed_exemptions[{index}].evidence_ids must be non-empty"
            )
        elif ledger_evidence_ids is not None:
            for evidence_id in evidence_ids:
                if evidence_id not in ledger_evidence_ids:
                    rule_errors.append(
                        f"reviewed_exemptions[{index}].evidence_ids does not resolve: "
                        f"{evidence_id}"
                    )
        exemption_keys[finding_id] = item
    active, exempted = [], []
    used_exemptions: set[str] = set()
    for finding in findings:
        exemption = exemption_keys.get(finding["finding_id"])
        if exemption:
            used_exemptions.add(finding["finding_id"])
            finding = {**finding, "exemption": exemption}
            exempted.append(finding)
        else:
            active.append(finding)
    unused_exemptions = [
        exemption_keys[key] for key in sorted(set(exemption_keys) - used_exemptions)
    ]
    counts = {
        severity: sum(item["severity"] == severity for item in active)
        for severity in ("high", "medium", "low")
    }
    return {
        "schema": "clews-connectivity-audit-v1",
        "case_dir": str(case_dir.resolve()),
        "scenario": scenario,
        "years": years,
        "technology_count": len(technologies),
        "commodity_count": len(commodities),
        "status": (
            "fail"
            if rule_errors or unused_exemptions
            else "findings"
            if active
            else "pass"
        ),
        "summary": {"active": len(active), "exempted": len(exempted), **counts},
        "findings": active,
        "reviewed_exemptions": exempted,
        "rule_errors": rule_errors,
        "unused_exemptions": unused_exemptions,
        "interpretation": "Findings are audit candidates. Resolve, declare with evidence, or defer in the schema ledger after equation and role review.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--ledger-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on", choices=("none", "high", "all"), default="none")
    args = parser.parse_args()
    try:
        ledger_ids = (
            read_ledger_evidence_ids(args.ledger_dir.resolve())
            if args.ledger_dir
            else None
        )
        report = audit(args.case_dir.resolve(), load(args.rules), ledger_ids)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if report["status"] == "fail":
        return 1
    if args.fail_on == "high" and report["summary"]["high"]:
        return 1
    if args.fail_on == "all" and report["summary"]["active"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
