#!/usr/bin/env python3
"""Validate an evidence-driven CLEWs country-calibration package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


PRE_SOLVE_GATES = (
    "identifier_integrity",
    "connectivity_review",
    "equation_unit_replay",
    "generated_data_inspection",
    "stock_resource_account_checks",
    "matrix_check",
    "schema_ledger_validation",
    "no_forcing_audit",
)
SOURCE_INPUT_PATCH_GATES = (
    "identifier_integrity",
    "generated_data_inspection",
    "schema_ledger_validation",
    "live_regeneration",
    "result_free_archive_identity",
)
PROMOTION_GATES = PRE_SOLVE_GATES + (
    "solver_run",
    "baseline_comparison",
    "live_regeneration",
    "result_free_archive_identity",
)
MATERIAL_STAGES = {"source-input-patch", "pre-solve", "promotion"}
FINDING_STATUSES = {"pending", "resolved", "declared", "exempted", "deferred"}
OPTIONAL_GATES = {"matrix_check", "stock_resource_account_checks"}
DELIVERY_STATES = {"working", "source_input_patch", "promoted"}
RESULT_STATUSES = {"absent", "stale", "fresh"}
REPORTING_LAYER_TYPES = {"solver_native", "postprocessed"}
CHANGE_TYPES = {
    "parameter_update",
    "object_addition",
    "object_retirement",
    "coupling_change",
}
EVIDENCE_ROLES = {
    "physical_input",
    "final_demand",
    "initial_stock",
    "documented_constraint",
    "transparent_proxy",
}
REGENERATION_CHANGE_CLASSES = {"metadata_only", "deterministic_regeneration"}
CORRECTABLE_FIELDS = {
    "SOURCES.csv": {
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
        "local_file",
        "sha256",
    }
}
COMPARISON_CLASSIFICATIONS = {
    "EXACT_PARITY",
    "STRUCTURAL_PARITY_ALTERNATE_OPTIMUM_CANDIDATE",
    "MATERIAL_CHANGE",
}
LEDGER_IDS = {
    "SOURCES.csv": "source_id",
    "CALCULATIONS.csv": "calculation_id",
    "ASSUMPTIONS.csv": "assumption_id",
    "MODEL_MAP.csv": "map_id",
    "GAPS.csv": "item",
    "CHANGES.csv": "change_id",
}


def require_text(
    container: dict[str, Any], field: str, location: str, errors: list[str]
) -> None:
    if not isinstance(container.get(field), str) or not container[field].strip():
        errors.append(f"{location}.{field} must be non-empty text")


def require_text_list(
    container: dict[str, Any],
    field: str,
    location: str,
    errors: list[str],
    *,
    nonempty: bool = True,
) -> list[str]:
    value = container.get(field)
    if (
        not isinstance(value, list)
        or (nonempty and not value)
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        qualifier = "a non-empty" if nonempty else "a"
        errors.append(f"{location}.{field} must be {qualifier} list of text")
        return []
    return value


def require_resolves(
    values: list[str], allowed: set[str], location: str, errors: list[str]
) -> None:
    for value in values:
        if value not in allowed:
            errors.append(f"{location} does not resolve: {value}")


def resolve(base_dir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else base_dir / path


def read_json(path: Path, location: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{location} is not readable JSON: {error}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{location} must contain a JSON object")
        return None
    return value


def read_ledger(
    ledger_dir: Path, errors: list[str]
) -> tuple[dict[str, set[str]], dict[str, dict[str, dict[str, str]]]]:
    ids: dict[str, set[str]] = {}
    rows_by_id: dict[str, dict[str, dict[str, str]]] = {}
    for filename, id_field in LEDGER_IDS.items():
        path = ledger_dir / filename
        try:
            with path.open(newline="", encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
        except OSError as error:
            errors.append(f"cannot read provenance ledger {path}: {error}")
            rows = []
        indexed = {
            row.get(id_field, "").strip(): row
            for row in rows
            if row.get(id_field, "").strip()
        }
        ids[filename] = set(indexed)
        rows_by_id[filename] = indexed
    return ids, rows_by_id


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def semantically_equal_json(before: Path, after: Path) -> bool:
    try:
        return json.loads(before.read_text(encoding="utf-8")) == json.loads(
            after.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return sha256(before) == sha256(after)


def changed_source_json(baseline: Path, candidate: Path) -> set[str]:
    before = {path.name: path for path in baseline.glob("*.json") if path.is_file()}
    after = {path.name: path for path in candidate.glob("*.json") if path.is_file()}
    return {
        name
        for name in set(before) | set(after)
        if name not in before
        or name not in after
        or not semantically_equal_json(before[name], after[name])
    }


def split_ids(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [item for item in re.split(r"[;,\s]+", value.strip()) if item]


def source_lineage(
    evidence_ids: list[str], ledger_rows: dict[str, dict[str, dict[str, str]]]
) -> set[str]:
    sources: set[str] = set()
    pending = list(evidence_ids)
    seen: set[str] = set()
    while pending:
        identifier = pending.pop()
        if identifier in seen:
            continue
        seen.add(identifier)
        if identifier in ledger_rows.get("SOURCES.csv", {}):
            sources.add(identifier)
        elif identifier in ledger_rows.get("CALCULATIONS.csv", {}):
            row = ledger_rows["CALCULATIONS.csv"][identifier]
            for field in ("source_ids", "assumption_ids", "input_calculation_ids"):
                pending.extend(split_ids(row.get(field)))
        elif identifier in ledger_rows.get("ASSUMPTIONS.csv", {}):
            pending.extend(
                split_ids(
                    ledger_rows["ASSUMPTIONS.csv"][identifier].get(
                        "evidence_source_ids"
                    )
                )
            )
    return sources


def validate_inheritance(
    predecessor: Path,
    current: Path,
    retained_evidence: Path,
    corrections: dict[tuple[str, str, str], dict[str, Any]],
    errors: list[str],
) -> None:
    used_corrections: set[tuple[str, str, str]] = set()
    predecessor_ids, predecessor_rows = read_ledger(predecessor, errors)
    current_ids, current_rows = read_ledger(current, errors)
    for filename, id_field in LEDGER_IDS.items():
        missing = sorted(predecessor_ids[filename] - current_ids[filename])
        if missing:
            errors.append(
                f"provenance inheritance dropped {filename} {id_field}s: {missing}"
            )
        if filename == "GAPS.csv":
            continue
        if filename == "MODEL_MAP.csv":
            ignored = {"superseded_by", "notes"}
        else:
            ignored = {"notes"}
        for identifier in sorted(predecessor_ids[filename] & current_ids[filename]):
            before = {
                key: value
                for key, value in predecessor_rows[filename][identifier].items()
                if key not in ignored
            }
            after = {
                key: value
                for key, value in current_rows[filename][identifier].items()
                if key not in ignored
            }
            differing = {
                field
                for field in set(before) | set(after)
                if before.get(field) != after.get(field)
            }
            for field in sorted(differing):
                correction = corrections.get((filename, identifier, field))
                if correction is None:
                    errors.append(
                        f"provenance inheritance altered retained {filename} row "
                        f"{identifier} field {field} without a correction record"
                    )
                    continue
                used_corrections.add((filename, identifier, field))
                if str(correction.get("before", "")) != str(before.get(field, "")):
                    errors.append(
                        f"provenance correction before value does not match "
                        f"{filename} {identifier} {field}"
                    )
                if str(correction.get("after", "")) != str(after.get(field, "")):
                    errors.append(
                        f"provenance correction after value does not match "
                        f"{filename} {identifier} {field}"
                    )
    for key in sorted(set(corrections) - used_corrections):
        errors.append(
            "provenance correction does not correspond to an inherited row change: "
            + "/".join(key)
        )
    previous_evidence = predecessor / "evidence"
    if not previous_evidence.is_dir():
        errors.append(
            f"predecessor retained evidence does not exist: {previous_evidence}"
        )
        return
    for source in sorted(
        path for path in previous_evidence.rglob("*") if path.is_file()
    ):
        relative = source.relative_to(previous_evidence)
        target = retained_evidence / relative
        if not target.is_file():
            errors.append(
                f"provenance inheritance dropped retained evidence: {relative}"
            )
        elif sha256(source) != sha256(target):
            errors.append(
                f"provenance inheritance altered retained evidence: {relative}"
            )


def validate_gate(
    gate: Any,
    location: str,
    required: bool,
    base_dir: Path,
    errors: list[str],
    *,
    gate_name: str | None = None,
) -> Path | None:
    if not isinstance(gate, dict):
        errors.append(f"{location} must be an object")
        return None
    status = gate.get("status")
    if status not in {"pending", "passed", "failed", "not_applicable"}:
        errors.append(f"{location}.status is invalid")
        return None
    if required and status not in {"passed", "not_applicable"}:
        errors.append(f"{location}.status must be passed or not_applicable")
        return None
    if status == "not_applicable":
        require_text(gate, "reason", location, errors)
        if required and gate_name not in OPTIONAL_GATES:
            errors.append(f"{location} is mandatory and cannot be not_applicable")
        return None
    if status == "passed":
        artifact = gate.get("artifact")
        if not isinstance(artifact, str) or not artifact.strip():
            errors.append(f"{location}.artifact is required when passed")
        elif not resolve(base_dir, artifact).is_file():
            errors.append(f"{location}.artifact does not exist: {artifact}")
        else:
            return resolve(base_dir, artifact)
    return None


def validate_report(
    path: Path | None,
    location: str,
    errors: list[str],
    *,
    schema: str | None = None,
    allowed_statuses: set[str] | None = None,
) -> dict[str, Any] | None:
    if path is None:
        return None
    report = read_json(path, f"{location}.artifact", errors)
    if report is None:
        return None
    if schema is not None and report.get("schema") != schema:
        errors.append(f"{location}.artifact schema must equal {schema}")
    statuses = {"pass"} if allowed_statuses is None else allowed_statuses
    if report.get("status") not in statuses:
        errors.append(f"{location}.artifact status must be one of {sorted(statuses)}")
    return report


def validate_package(
    package: Any,
    stage: str,
    package_dir: Path | None = None,
    case_dir: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    root = case_dir if case_dir is not None else package_dir
    base_dir = Path(root).expanduser().resolve() if root else Path.cwd()
    ledger_ids: dict[str, set[str]] = {}
    ledger_rows: dict[str, dict[str, dict[str, str]]] = {}
    ledger_dir: Path | None = None
    if not isinstance(package, dict):
        return ["package root must be a JSON object"]
    if package.get("schema_version") != 3:
        errors.append("schema_version must equal 3")
    regeneration_changes = package.get("regeneration_changes")
    if not isinstance(regeneration_changes, list):
        errors.append("regeneration_changes must be a list")
        regeneration_changes = []

    case = package.get("case")
    if not isinstance(case, dict):
        errors.append("case must be an object")
    else:
        for field in (
            "source_case",
            "candidate_case",
            "baseline_run",
            "source_json_dir",
            "candidate_json_dir",
            "scenario",
            "horizon",
            "intended_use",
        ):
            require_text(case, field, "case", errors)
        if case.get("source_case") == case.get("candidate_case"):
            errors.append(
                "case.candidate_case must be disposable and distinct from source_case"
            )
        if stage in MATERIAL_STAGES:
            source_dirs: dict[str, Path] = {}
            for field in ("source_json_dir", "candidate_json_dir"):
                value = case.get(field)
                if isinstance(value, str) and value.strip():
                    source_dirs[field] = resolve(base_dir, value).resolve()
                    if not source_dirs[field].is_dir():
                        errors.append(f"case.{field} does not exist: {value}")
            if len(source_dirs) == 2:
                changed_files = changed_source_json(
                    source_dirs["source_json_dir"], source_dirs["candidate_json_dir"]
                )
                if not list(source_dirs["source_json_dir"].glob("*.json")) and not list(
                    source_dirs["candidate_json_dir"].glob("*.json")
                ):
                    errors.append("case source JSON directories contain no JSON files")
                declared_files = {
                    item.get("source_file")
                    for item in package.get("changes", [])
                    if isinstance(item, dict)
                    and isinstance(item.get("source_file"), str)
                }
                regeneration_files = {
                    item.get("source_file")
                    for item in regeneration_changes
                    if isinstance(item, dict)
                    and isinstance(item.get("source_file"), str)
                }
                overlap = declared_files & regeneration_files
                if overlap:
                    errors.append(
                        "source files cannot be both model changes and regeneration changes: "
                        f"{sorted(overlap)}"
                    )
                declared_files |= regeneration_files
                if changed_files != declared_files:
                    errors.append(
                        "actual changed source JSON files must exactly match changes[].source_file: "
                        f"actual={sorted(changed_files)} declared={sorted(declared_files)}"
                    )
                if isinstance(regeneration_changes, list):
                    for index, item in enumerate(regeneration_changes):
                        location = f"regeneration_changes[{index}]"
                        if not isinstance(item, dict):
                            errors.append(f"{location} must be an object")
                            continue
                        for field in (
                            "source_file",
                            "before_sha256",
                            "after_sha256",
                            "classification",
                            "reason",
                        ):
                            require_text(item, field, location, errors)
                        if item.get("classification") not in REGENERATION_CHANGE_CLASSES:
                            errors.append(
                                f"{location}.classification must be one of "
                                f"{sorted(REGENERATION_CHANGE_CLASSES)}"
                            )
                        name = item.get("source_file")
                        if isinstance(name, str):
                            before = source_dirs["source_json_dir"] / name
                            after = source_dirs["candidate_json_dir"] / name
                            if not before.is_file() or not after.is_file():
                                errors.append(
                                    f"{location}.source_file must exist on both sides"
                                )
                            else:
                                if item.get("before_sha256") != sha256(before):
                                    errors.append(
                                        f"{location}.before_sha256 does not match source"
                                    )
                                if item.get("after_sha256") != sha256(after):
                                    errors.append(
                                        f"{location}.after_sha256 does not match candidate"
                                    )

    provenance = package.get("provenance")
    corrections_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    inherited_coverage_gaps: set[str] = set()
    if not isinstance(provenance, dict):
        errors.append("provenance must be an object")
    else:
        for field in (
            "inherited_ledger_dir",
            "predecessor_ledger_dir",
            "retained_evidence_dir",
        ):
            require_text(provenance, field, "provenance", errors)
        corrections = provenance.get("corrections")
        if not isinstance(corrections, list):
            errors.append("provenance.corrections must be a list")
            corrections = []
        for index, item in enumerate(corrections):
            location = f"provenance.corrections[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{location} must be an object")
                continue
            for field in ("table", "id", "field", "reason", "evidence_artifact"):
                require_text(item, field, location, errors)
            if "before" not in item or "after" not in item:
                errors.append(f"{location}.before and .after are required")
            table, identifier, field = (
                item.get("table"),
                item.get("id"),
                item.get("field"),
            )
            if (
                table not in CORRECTABLE_FIELDS
                or field not in CORRECTABLE_FIELDS.get(str(table), set())
            ):
                errors.append(
                    f"{location} may correct only approved source-metadata fields; "
                    "create or supersede a ledger record for numerical or lineage changes"
                )
            if all(isinstance(value, str) and value for value in (table, identifier, field)):
                key = (table, identifier, field)
                if key in corrections_by_key:
                    errors.append(f"{location} duplicates correction {'/'.join(key)}")
                corrections_by_key[key] = item
            artifact = item.get("evidence_artifact")
            if (
                stage in MATERIAL_STAGES
                and isinstance(artifact, str)
                and artifact.strip()
                and not resolve(base_dir, artifact).is_file()
            ):
                errors.append(f"{location}.evidence_artifact does not exist: {artifact}")

        coverage_gaps = provenance.get("inherited_coverage_gaps")
        if not isinstance(coverage_gaps, list):
            errors.append("provenance.inherited_coverage_gaps must be a list")
            coverage_gaps = []
        for index, item in enumerate(coverage_gaps):
            location = f"provenance.inherited_coverage_gaps[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{location} must be an object")
                continue
            for field in ("model_file", "reason", "backlog_item"):
                require_text(item, field, location, errors)
            model_file = item.get("model_file")
            if isinstance(model_file, str) and model_file.strip():
                if model_file in inherited_coverage_gaps:
                    errors.append(f"{location}.model_file duplicates {model_file}")
                inherited_coverage_gaps.add(model_file)
        if stage in MATERIAL_STAGES:
            resolved: dict[str, Path] = {}
            for field in (
                "inherited_ledger_dir",
                "predecessor_ledger_dir",
                "retained_evidence_dir",
            ):
                value = provenance.get(field)
                if isinstance(value, str) and value.strip():
                    resolved[field] = resolve(base_dir, value).resolve()
                    if not resolved[field].is_dir():
                        errors.append(f"provenance.{field} does not exist: {value}")
            ledger_dir = resolved.get("inherited_ledger_dir")
            predecessor = resolved.get("predecessor_ledger_dir")
            retained = resolved.get("retained_evidence_dir")
            if ledger_dir and ledger_dir.is_dir():
                ledger_ids, ledger_rows = read_ledger(ledger_dir, errors)
            if (
                ledger_dir
                and predecessor
                and retained
                and ledger_dir.is_dir()
                and predecessor.is_dir()
                and retained.is_dir()
            ):
                validate_inheritance(
                    predecessor,
                    ledger_dir,
                    retained,
                    corrections_by_key,
                    errors,
                )

    backlog = package.get("backlog")
    backlog_ids: set[str] = set()
    if not isinstance(backlog, dict):
        errors.append("backlog must be an object")
    else:
        require_text(backlog, "path", "backlog", errors)
        require_text(backlog, "prioritization_basis", "backlog", errors)
        if stage in MATERIAL_STAGES:
            value = backlog.get("path")
            if (
                isinstance(value, str)
                and value.strip()
                and not resolve(base_dir, value).is_file()
            ):
                errors.append(f"backlog.path does not exist: {value}")
            elif isinstance(value, str) and value.strip():
                try:
                    with resolve(base_dir, value).open(
                        newline="", encoding="utf-8-sig"
                    ) as stream:
                        backlog_ids = {
                            row.get("item_id", "").strip()
                            for row in csv.DictReader(stream)
                            if row.get("item_id", "").strip()
                        }
                except OSError as error:
                    errors.append(f"cannot read backlog {value}: {error}")
        if isinstance(provenance, dict):
            for index, item in enumerate(
                provenance.get("inherited_coverage_gaps", [])
                if isinstance(provenance.get("inherited_coverage_gaps"), list)
                else []
            ):
                if (
                    stage in MATERIAL_STAGES
                    and isinstance(item, dict)
                    and item.get("backlog_item") not in backlog_ids
                ):
                    errors.append(
                        f"provenance.inherited_coverage_gaps[{index}].backlog_item "
                        "does not resolve"
                    )

    packages = package.get("packages")
    package_ids: set[str] = set()
    package_finding_ids: set[str] = set()
    if not isinstance(packages, list) or not packages:
        errors.append("packages must be a non-empty list")
        packages = []
    for index, item in enumerate(packages):
        location = f"packages[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location} must be an object")
            continue
        for field in (
            "package_id",
            "name",
            "current_weakness",
            "objective",
            "coherence_basis",
            "completion_test",
            "claim_scope",
        ):
            require_text(item, field, location, errors)
        package_id = item.get("package_id")
        if isinstance(package_id, str):
            if package_id in package_ids:
                errors.append(f"{location}.package_id duplicates {package_id}")
            package_ids.add(package_id)
        require_text_list(item, "affected_sectors", location, errors)
        temporal = item.get("temporal_boundary")
        if not isinstance(temporal, dict):
            errors.append(f"{location}.temporal_boundary must be an object")
        else:
            require_text(
                temporal,
                "evidence_period",
                f"{location}.temporal_boundary",
                errors,
            )
            latest_year = temporal.get("latest_evidence_year")
            if not isinstance(latest_year, int) or isinstance(latest_year, bool):
                errors.append(
                    f"{location}.temporal_boundary.latest_evidence_year must be an integer"
                )
            require_text(
                temporal,
                "post_evidence_treatment",
                f"{location}.temporal_boundary",
                errors,
            )
        evidence_boundary = item.get("evidence_boundary")
        if not isinstance(evidence_boundary, dict):
            errors.append(f"{location}.evidence_boundary must be an object")
        else:
            for field in (
                "geography",
                "quantity",
                "allocation_rule",
                "quality_status",
            ):
                require_text(
                    evidence_boundary,
                    field,
                    f"{location}.evidence_boundary",
                    errors,
                )
        invariants = item.get("invariants")
        if not isinstance(invariants, list) or not invariants:
            errors.append(f"{location}.invariants must be a non-empty list")
        else:
            invariant_names: set[str] = set()
            for invariant_index, invariant in enumerate(invariants):
                invariant_location = f"{location}.invariants[{invariant_index}]"
                if not isinstance(invariant, dict):
                    errors.append(f"{invariant_location} must be an object")
                    continue
                for field in ("name", "metric", "acceptance_rule"):
                    require_text(invariant, field, invariant_location, errors)
                name = invariant.get("name")
                if isinstance(name, str):
                    if name in invariant_names:
                        errors.append(f"{invariant_location}.name duplicates {name}")
                    invariant_names.add(name)
        package_finding_ids.update(
            require_text_list(
                item, "connectivity_finding_ids", location, errors, nonempty=False
            )
        )

    changes = package.get("changes")
    change_ids: set[str] = set()
    change_source_lineages: dict[str, set[str]] = {}
    change_benchmark_exceptions: dict[str, set[str]] = {}
    if not isinstance(changes, list) or not changes:
        errors.append("changes must be a non-empty list")
        changes = []
    for index, item in enumerate(changes):
        location = f"changes[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location} must be an object")
            continue
        for field in (
            "change_id",
            "package_id",
            "parameter",
            "source_file",
            "coordinates",
            "model_unit",
            "physical_effect",
            "evidence_role",
            "counterfactual_reason",
        ):
            require_text(item, field, location, errors)
        if item.get("evidence_role") not in EVIDENCE_ROLES:
            errors.append(
                f"{location}.evidence_role must be one of {sorted(EVIDENCE_ROLES)}"
            )
        change_type = item.get("change_type", "parameter_update")
        if change_type not in CHANGE_TYPES:
            errors.append(
                f"{location}.change_type must be one of {sorted(CHANGE_TYPES)}"
            )
        if change_type == "object_retirement":
            require_text_list(item, "retired_object_ids", location, errors)
            for field in (
                "reference_inventory_artifact",
                "inactivity_evidence_artifact",
            ):
                require_text(item, field, location, errors)
                artifact = item.get(field)
                if (
                    stage in MATERIAL_STAGES
                    and isinstance(artifact, str)
                    and artifact.strip()
                    and not resolve(base_dir, artifact).is_file()
                ):
                    errors.append(f"{location}.{field} does not exist: {artifact}")
        change_id = item.get("change_id")
        if isinstance(change_id, str):
            if change_id in change_ids:
                errors.append(f"{location}.change_id duplicates {change_id}")
            change_ids.add(change_id)
        if item.get("package_id") not in package_ids:
            errors.append(f"{location}.package_id does not resolve")
        require_text_list(item, "local_equations", location, errors)
        evidence_ids = require_text_list(item, "evidence_ids", location, errors)
        model_map_ids = require_text_list(item, "model_map_ids", location, errors)
        exception_ids: set[str] = set()
        exceptions = item.get("benchmark_source_exceptions")
        if not isinstance(exceptions, list):
            errors.append(f"{location}.benchmark_source_exceptions must be a list")
            exceptions = []
        for exception_index, exception in enumerate(exceptions):
            exception_location = (
                f"{location}.benchmark_source_exceptions[{exception_index}]"
            )
            if not isinstance(exception, dict):
                errors.append(f"{exception_location} must be an object")
                continue
            require_text(exception, "source_id", exception_location, errors)
            require_text(exception, "reason", exception_location, errors)
            source_id = exception.get("source_id")
            if isinstance(source_id, str):
                if source_id in exception_ids:
                    errors.append(
                        f"{exception_location}.source_id duplicates {source_id}"
                    )
                exception_ids.add(source_id)
        if isinstance(change_id, str):
            change_benchmark_exceptions[change_id] = exception_ids
        if stage in MATERIAL_STAGES and ledger_ids:
            evidence = set().union(
                ledger_ids["SOURCES.csv"],
                ledger_ids["CALCULATIONS.csv"],
                ledger_ids["ASSUMPTIONS.csv"],
            )
            require_resolves(evidence_ids, evidence, f"{location}.evidence_ids", errors)
            if isinstance(change_id, str):
                change_source_lineages[change_id] = source_lineage(
                    evidence_ids, ledger_rows
                )
            require_resolves(
                model_map_ids,
                ledger_ids["MODEL_MAP.csv"],
                f"{location}.model_map_ids",
                errors,
            )
            if (
                isinstance(change_id, str)
                and change_id not in ledger_ids["CHANGES.csv"]
            ):
                errors.append(f"{location}.change_id does not resolve: {change_id}")
            for map_id in model_map_ids:
                row = ledger_rows["MODEL_MAP.csv"].get(map_id)
                if not row:
                    continue
                source_file = str(item.get("source_file", "")).replace("\\", "/")
                model_file = row.get("model_file", "").replace("\\", "/")
                if source_file and not (
                    model_file == source_file or model_file.endswith("/" + source_file)
                ):
                    errors.append(
                        f"{location}.model_map_ids {map_id} maps {model_file}, not {source_file}"
                    )
                if row.get("parameter") != item.get("parameter"):
                    errors.append(
                        f"{location}.model_map_ids {map_id} maps parameter "
                        f"{row.get('parameter')}, not {item.get('parameter')}"
                    )

    benchmarks = package.get("benchmarks")
    benchmark_source_ids: set[str] = set()
    if not isinstance(benchmarks, list):
        errors.append("benchmarks must be a list")
        benchmarks = []
    for index, item in enumerate(benchmarks):
        location = f"benchmarks[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location} must be an object")
            continue
        require_text(item, "name", location, errors)
        source_ids = require_text_list(item, "source_ids", location, errors)
        benchmark_source_ids.update(source_ids)
        if item.get("diagnostic_only") is not True:
            errors.append(f"{location}.diagnostic_only must be true")
        if stage in MATERIAL_STAGES and ledger_ids:
            require_resolves(
                source_ids, ledger_ids["SOURCES.csv"], f"{location}.source_ids", errors
            )

    if stage in MATERIAL_STAGES and ledger_ids:
        for change_id, lineage_sources in change_source_lineages.items():
            overlap = lineage_sources & benchmark_source_ids
            exceptions = change_benchmark_exceptions.get(change_id, set())
            missing = sorted(overlap - exceptions)
            unused = sorted(exceptions - overlap)
            if missing:
                errors.append(
                    f"change {change_id} uses diagnostic benchmark sources in its "
                    f"transitive evidence lineage without explicit physical-use reasons: {missing}"
                )
            if unused:
                errors.append(
                    f"change {change_id} declares unused benchmark-source exceptions: {unused}"
                )

    reporting_layers = package.get("reporting_layers", [])
    has_postprocessed_layers = False
    layer_ids: set[str] = set()
    if not isinstance(reporting_layers, list):
        errors.append("reporting_layers must be a list")
        reporting_layers = []
    for index, item in enumerate(reporting_layers):
        location = f"reporting_layers[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location} must be an object")
            continue
        for field in ("layer_id", "purpose", "type"):
            require_text(item, field, location, errors)
        layer_id = item.get("layer_id")
        if isinstance(layer_id, str):
            if layer_id in layer_ids:
                errors.append(f"{location}.layer_id duplicates {layer_id}")
            layer_ids.add(layer_id)
        layer_type = item.get("type")
        if layer_type not in REPORTING_LAYER_TYPES:
            errors.append(
                f"{location}.type must be one of {sorted(REPORTING_LAYER_TYPES)}"
            )
        require_text_list(item, "raw_inputs", location, errors)
        require_text_list(item, "published_outputs", location, errors)
        if layer_type == "postprocessed":
            has_postprocessed_layers = True
            for field in ("publisher_script", "publisher_version", "manifest"):
                require_text(item, field, location, errors)
            if item.get("rerun_after_every_solve") is not True:
                errors.append(f"{location}.rerun_after_every_solve must be true")

    connectivity = package.get("connectivity")
    dispositions_by_id: dict[str, dict[str, Any]] = {}
    if not isinstance(connectivity, dict):
        errors.append("connectivity must be an object")
    else:
        require_text(connectivity, "rules", "connectivity", errors)
        dispositions = connectivity.get("finding_dispositions")
        disposition_ids: set[str] = set()
        if not isinstance(dispositions, list):
            errors.append("connectivity.finding_dispositions must be a list")
            dispositions = []
        for index, item in enumerate(dispositions):
            location = f"connectivity.finding_dispositions[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{location} must be an object")
                continue
            require_text(item, "finding_id", location, errors)
            require_text(item, "resolution", location, errors)
            status = item.get("status")
            finding_id = item.get("finding_id")
            if isinstance(finding_id, str):
                if finding_id in disposition_ids:
                    errors.append(f"{location}.finding_id duplicates {finding_id}")
                disposition_ids.add(finding_id)
                dispositions_by_id[finding_id] = item
            if status not in FINDING_STATUSES:
                errors.append(
                    f"{location}.status must be one of {sorted(FINDING_STATUSES)}"
                )
            if stage in {"pre-solve", "promotion"} and status == "pending":
                errors.append(f"{location}.status cannot remain pending at {stage}")
            evidence = require_text_list(
                item, "evidence_ids", location, errors, nonempty=False
            )
            gap_items = require_text_list(
                item, "gap_items", location, errors, nonempty=False
            )
            if (
                stage == "promotion"
                and status in {"resolved", "declared", "exempted"}
                and not evidence
            ):
                errors.append(f"{location}.evidence_ids are required at promotion")
            if stage in {"pre-solve", "promotion"} and status == "deferred":
                if not gap_items:
                    errors.append(
                        f"{location}.gap_items are required for a deferred finding"
                    )
            elif gap_items:
                errors.append(
                    f"{location}.gap_items are only valid for a deferred finding"
                )
            if stage in {"pre-solve", "promotion"} and ledger_ids:
                lineage = set().union(
                    ledger_ids["SOURCES.csv"],
                    ledger_ids["CALCULATIONS.csv"],
                    ledger_ids["ASSUMPTIONS.csv"],
                )
                require_resolves(evidence, lineage, f"{location}.evidence_ids", errors)
                require_resolves(
                    gap_items,
                    ledger_ids["GAPS.csv"],
                    f"{location}.gap_items",
                    errors,
                )

    non_forcing = package.get("non_forcing")
    if not isinstance(non_forcing, dict):
        errors.append("non_forcing must be an object")
    else:
        dispositions = non_forcing.get("candidate_dispositions")
        if not isinstance(dispositions, list):
            errors.append("non_forcing.candidate_dispositions must be a list")
            dispositions = []
        candidate_ids: set[str] = set()
        for index, item in enumerate(dispositions):
            location = f"non_forcing.candidate_dispositions[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{location} must be an object")
                continue
            for field in ("candidate_id", "status", "reason"):
                require_text(item, field, location, errors)
            candidate_id = item.get("candidate_id")
            if isinstance(candidate_id, str):
                if candidate_id in candidate_ids:
                    errors.append(f"{location}.candidate_id duplicates {candidate_id}")
                candidate_ids.add(candidate_id)
            status = item.get("status")
            if status not in {"allowed_physical_input", "fixed", "rejected"}:
                errors.append(f"{location}.status is invalid")
            evidence = require_text_list(
                item, "evidence_ids", location, errors, nonempty=False
            )
            if status == "allowed_physical_input" and not evidence:
                errors.append(
                    f"{location}.evidence_ids are required for allowed physical inputs"
                )
            if stage in MATERIAL_STAGES and ledger_ids:
                lineage = set().union(
                    ledger_ids["SOURCES.csv"],
                    ledger_ids["CALCULATIONS.csv"],
                    ledger_ids["ASSUMPTIONS.csv"],
                )
                require_resolves(evidence, lineage, f"{location}.evidence_ids", errors)

    runtime = package.get("runtime")
    if not isinstance(runtime, dict):
        errors.append("runtime must be an object")
    else:
        require_text(runtime, "wave_id", "runtime", errors)
        for field in ("known_good_seconds", "candidate_budget_seconds"):
            value = runtime.get(field)
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f"runtime.{field} must be positive")
        require_text(runtime, "baseline_artifact", "runtime", errors)
        limit = runtime.get("repair_solve_limit")
        used = runtime.get("repair_solves_used")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            errors.append("runtime.repair_solve_limit must be a positive integer")
        if not isinstance(used, int) or isinstance(used, bool) or used < 0:
            errors.append("runtime.repair_solves_used must be a nonnegative integer")
        if isinstance(limit, int) and isinstance(used, int) and used > limit:
            authorization = runtime.get("additional_solve_authorization")
            if not isinstance(authorization, str) or not authorization.strip():
                errors.append(
                    "runtime.additional_solve_authorization is required when the "
                    "repair solve limit is exceeded"
                )

    delivery = package.get("delivery")
    if not isinstance(delivery, dict):
        errors.append("delivery must be an object")
    else:
        state = delivery.get("state")
        if state not in DELIVERY_STATES:
            errors.append(f"delivery.state must be one of {sorted(DELIVERY_STATES)}")
        require_text(delivery, "history_artifact", "delivery", errors)
        result_status = delivery.get("result_status")
        if result_status not in RESULT_STATUSES:
            errors.append(
                f"delivery.result_status must be one of {sorted(RESULT_STATUSES)}"
            )
        require_text(delivery, "recertification_command", "delivery", errors)
        alternate_decision = delivery.get("alternate_optimum_decision")
        if alternate_decision is not None:
            if not isinstance(alternate_decision, dict):
                errors.append("delivery.alternate_optimum_decision must be an object")
            else:
                if not isinstance(alternate_decision.get("accepted"), bool):
                    errors.append(
                        "delivery.alternate_optimum_decision.accepted must be boolean"
                    )
                rationale = alternate_decision.get("rationale")
                if rationale is not None and (
                    not isinstance(rationale, str) or not rationale.strip()
                ):
                    errors.append(
                        "delivery.alternate_optimum_decision.rationale must be null "
                        "or non-empty text"
                    )
                artifact = alternate_decision.get("comparison_artifact")
                if artifact is not None and (
                    not isinstance(artifact, str) or not artifact.strip()
                ):
                    errors.append(
                        "delivery.alternate_optimum_decision.comparison_artifact "
                        "must be null or non-empty text"
                    )
        if stage == "source-input-patch":
            if state != "source_input_patch":
                errors.append(
                    "delivery.state must equal source_input_patch at source-input-patch"
                )
            if result_status not in {"absent", "stale"}:
                errors.append(
                    "delivery.result_status must be absent or stale at source-input-patch"
                )
        elif stage == "promotion":
            if state != "promoted":
                errors.append("delivery.state must equal promoted at promotion")
            if result_status != "fresh":
                errors.append("delivery.result_status must equal fresh at promotion")
        if stage in {"source-input-patch", "promotion"}:
            history = delivery.get("history_artifact")
            if (
                isinstance(history, str)
                and history.strip()
                and not resolve(base_dir, history).is_file()
            ):
                errors.append(f"delivery.history_artifact does not exist: {history}")

    gates = package.get("gates")
    gate_reports: dict[str, dict[str, Any]] = {}
    if not isinstance(gates, dict):
        errors.append("gates must be an object")
    else:
        required_names = set(PROMOTION_GATES)
        missing = sorted(required_names - set(gates))
        if missing:
            errors.append(f"gates missing required entries: {missing}")
        required = set()
        if stage == "source-input-patch":
            required = set(SOURCE_INPUT_PATCH_GATES)
        elif stage == "pre-solve":
            required = set(PRE_SOLVE_GATES)
        elif stage == "promotion":
            required = set(PROMOTION_GATES)
        for name in PROMOTION_GATES:
            if name in gates:
                path = validate_gate(
                    gates[name],
                    f"gates.{name}",
                    name in required,
                    base_dir,
                    errors,
                    gate_name=name,
                )
                if name == "connectivity_review":
                    report = validate_report(
                        path,
                        f"gates.{name}",
                        errors,
                        schema="clews-connectivity-audit-v1",
                        allowed_statuses={"pass", "findings"},
                    )
                elif name == "baseline_comparison":
                    report = validate_report(
                        path,
                        f"gates.{name}",
                        errors,
                        schema="clews-run-comparison-v2",
                    )
                elif name == "stock_resource_account_checks":
                    report = validate_report(
                        path,
                        f"gates.{name}",
                        errors,
                        schema="clews-resource-account-validation-v1",
                    )
                elif name == "no_forcing_audit":
                    report = validate_report(
                        path,
                        f"gates.{name}",
                        errors,
                        schema="clews-non-forcing-audit-v1",
                    )
                else:
                    report = validate_report(path, f"gates.{name}", errors)
                if report is not None:
                    gate_reports[name] = report

        reporting_gate = gates.get("reporting_layers_current")
        if reporting_gate is None:
            if has_postprocessed_layers:
                errors.append(
                    "gates.reporting_layers_current is required when a "
                    "postprocessed reporting layer is declared"
                )
        else:
            path = validate_gate(
                reporting_gate,
                "gates.reporting_layers_current",
                stage == "promotion" and has_postprocessed_layers,
                base_dir,
                errors,
                gate_name="reporting_layers_current",
            )
            report = validate_report(
                path,
                "gates.reporting_layers_current",
                errors,
                schema="clews-reporting-layer-validation-v1",
            )
            if report is not None:
                gate_reports["reporting_layers_current"] = report

    if stage in MATERIAL_STAGES:
        rules = connectivity.get("rules") if isinstance(connectivity, dict) else None
        if (
            stage in {"pre-solve", "promotion"}
            and isinstance(rules, str)
            and rules.strip()
            and not resolve(base_dir, rules).is_file()
        ):
            errors.append(f"connectivity.rules does not exist: {rules}")

        case_data = case if isinstance(case, dict) else {}
        connectivity_report = gate_reports.get("connectivity_review")
        if connectivity_report:
            reported_case_value = connectivity_report.get("case_dir")
            if not isinstance(reported_case_value, str) or not reported_case_value:
                errors.append(
                    "gates.connectivity_review artifact.case_dir must be non-empty"
                )
            else:
                reported_case = Path(reported_case_value)
                if not reported_case.is_absolute():
                    reported_case = resolve(base_dir, str(reported_case))
                if reported_case.resolve() != base_dir.resolve():
                    errors.append(
                        "gates.connectivity_review artifact case_dir does not match case root"
                    )
            if connectivity_report.get("scenario") != case_data.get("scenario"):
                errors.append(
                    "gates.connectivity_review artifact scenario does not match case"
                )
            if connectivity_report.get("rule_errors"):
                errors.append("gates.connectivity_review artifact contains rule_errors")
            if connectivity_report.get("unused_exemptions"):
                errors.append(
                    "gates.connectivity_review artifact contains unused_exemptions"
                )
            active_findings = connectivity_report.get("findings", [])
            exempted_findings = connectivity_report.get("reviewed_exemptions", [])
            if not isinstance(active_findings, list) or not isinstance(
                exempted_findings, list
            ):
                errors.append("gates.connectivity_review artifact findings are invalid")
            else:
                active_ids = {
                    item.get("finding_id")
                    for item in active_findings
                    if isinstance(item, dict)
                    and isinstance(item.get("finding_id"), str)
                }
                audit_ids = active_ids | {
                    item.get("finding_id")
                    for item in exempted_findings
                    if isinstance(item, dict)
                    and isinstance(item.get("finding_id"), str)
                }
                exempted_ids = audit_ids - active_ids
                retained_resolved_ids = {
                    finding_id
                    for finding_id, disposition in dispositions_by_id.items()
                    if disposition.get("status") == "resolved"
                }
                require_resolves(
                    sorted(package_finding_ids),
                    audit_ids | retained_resolved_ids,
                    "packages[].connectivity_finding_ids",
                    errors,
                )
                for finding_id in sorted(active_ids):
                    disposition = dispositions_by_id.get(finding_id)
                    if disposition is None:
                        errors.append(
                            f"connectivity finding has no disposition: {finding_id}"
                        )
                    elif disposition.get("status") == "pending":
                        errors.append(
                            f"connectivity finding disposition remains pending: {finding_id}"
                        )
                    elif disposition.get("status") == "exempted":
                        errors.append(
                            f"active connectivity finding cannot be marked exempted: {finding_id}"
                        )
                for finding_id in sorted(set(dispositions_by_id) - active_ids):
                    disposition = dispositions_by_id[finding_id]
                    status = disposition.get("status")
                    if finding_id in exempted_ids:
                        if status not in {"exempted", "declared"}:
                            errors.append(
                                f"reviewed exemption disposition must be exempted or declared: {finding_id}"
                            )
                    elif status != "resolved":
                        errors.append(
                            "connectivity disposition is neither active, reviewed-exempt, "
                            f"nor retained resolved history: {finding_id}"
                        )

        provenance_report = gate_reports.get("schema_ledger_validation")
        if provenance_report and ledger_dir:
            reported = Path(str(provenance_report.get("ledger_dir", ""))).expanduser()
            if not reported.is_absolute():
                reported = resolve(base_dir, str(reported))
            if reported.resolve() != ledger_dir.resolve():
                errors.append(
                    "gates.schema_ledger_validation artifact ledger_dir does not match provenance.inherited_ledger_dir"
                )
            allowed_stages = (
                {"delivery"} if stage == "promotion" else {"build", "delivery"}
            )
            if provenance_report.get("stage") not in allowed_stages:
                errors.append(
                    f"gates.schema_ledger_validation artifact stage must be one of {sorted(allowed_stages)}"
                )
            coverage = provenance_report.get("model_inputs")
            if not isinstance(coverage, dict):
                errors.append(
                    "gates.schema_ledger_validation artifact must report model-input coverage"
                )
            else:
                uncovered = coverage.get("uncovered_inputs")
                required_uncovered = coverage.get("uncovered_required_inputs", [])
                legacy = coverage.get("legacy_uncovered_inputs", [])
                if not all(
                    isinstance(value, list)
                    for value in (uncovered, required_uncovered, legacy)
                ):
                    errors.append(
                        "gates.schema_ledger_validation artifact coverage lists are invalid"
                    )
                elif required_uncovered:
                    errors.append(
                        "gates.schema_ledger_validation artifact leaves touched inputs uncovered"
                    )
                elif stage == "promotion":
                    if uncovered:
                        errors.append(
                            "promotion requires complete model-input coverage"
                        )
                    if inherited_coverage_gaps:
                        errors.append(
                            "promotion cannot retain inherited provenance coverage gaps"
                        )
                elif set(legacy) != inherited_coverage_gaps:
                    errors.append(
                        "documented inherited coverage gaps must exactly match the "
                        "provenance report's legacy_uncovered_inputs"
                    )

        no_forcing_report = gate_reports.get("no_forcing_audit")
        if no_forcing_report:
            reported_case = Path(str(no_forcing_report.get("case_dir", "")))
            if not reported_case.is_absolute():
                reported_case = resolve(base_dir, str(reported_case))
            if reported_case.resolve() != base_dir.resolve():
                errors.append(
                    "gates.no_forcing_audit artifact case_dir does not match case root"
                )
            for field, label in (
                ("unresolved_candidates", "unresolved candidates"),
                ("invalid_dispositions", "invalid dispositions"),
                ("prohibited_solve_attempts", "prohibited solve attempts"),
                ("benchmark_lineage_failures", "benchmark-lineage failures"),
            ):
                value = no_forcing_report.get(field)
                if not isinstance(value, list):
                    errors.append(
                        f"gates.no_forcing_audit artifact.{field} must be a list"
                    )
                elif value:
                    errors.append(
                        f"gates.no_forcing_audit artifact contains {label}"
                    )

        comparison = gate_reports.get("baseline_comparison")
        if comparison:
            if comparison.get("common_file_count", 0) < 1:
                errors.append(
                    "gates.baseline_comparison artifact compares no common tables"
                )
            for field in ("baseline_only", "candidate_only"):
                if not isinstance(comparison.get(field), list):
                    errors.append(
                        f"gates.baseline_comparison artifact.{field} must be a list"
                    )
            classification = comparison.get("classification")
            if classification not in COMPARISON_CLASSIFICATIONS:
                errors.append(
                    "gates.baseline_comparison artifact.classification must be one "
                    f"of {sorted(COMPARISON_CLASSIFICATIONS)}"
                )
            for field in ("strict_row_parity", "structural_parity"):
                if not isinstance(comparison.get(field), bool):
                    errors.append(
                        f"gates.baseline_comparison artifact.{field} must be boolean"
                    )
            strict_parity = comparison.get("strict_row_parity")
            structural_parity = comparison.get("structural_parity")
            expected_parity = {
                "EXACT_PARITY": (True, True),
                "STRUCTURAL_PARITY_ALTERNATE_OPTIMUM_CANDIDATE": (False, True),
                "MATERIAL_CHANGE": (False, False),
            }.get(classification)
            if (
                expected_parity
                and (
                    strict_parity,
                    structural_parity,
                )
                != expected_parity
            ):
                errors.append(
                    "gates.baseline_comparison artifact parity flags are inconsistent "
                    f"with classification {classification}"
                )
            if (
                stage == "promotion"
                and classification == "STRUCTURAL_PARITY_ALTERNATE_OPTIMUM_CANDIDATE"
            ):
                decision = (
                    delivery.get("alternate_optimum_decision")
                    if isinstance(delivery, dict)
                    else None
                )
                if (
                    not isinstance(decision, dict)
                    or decision.get("accepted") is not True
                ):
                    errors.append(
                        "delivery.alternate_optimum_decision must explicitly accept "
                        "the alternate-optimum candidate at promotion"
                    )
                else:
                    artifact = decision.get("comparison_artifact")
                    rationale = decision.get("rationale")
                    gate_artifact = (
                        gates.get("baseline_comparison", {}).get("artifact")
                        if isinstance(gates, dict)
                        else None
                    )
                    if not isinstance(artifact, str) or not artifact.strip():
                        errors.append(
                            "delivery.alternate_optimum_decision.comparison_artifact "
                            "is required at promotion"
                        )
                    if not isinstance(rationale, str) or not rationale.strip():
                        errors.append(
                            "delivery.alternate_optimum_decision.rationale is required "
                            "at promotion"
                        )
                    elif not isinstance(gate_artifact, str) or (
                        resolve(base_dir, artifact).resolve()
                        != resolve(base_dir, gate_artifact).resolve()
                    ):
                        errors.append(
                            "delivery.alternate_optimum_decision.comparison_artifact "
                            "must match gates.baseline_comparison.artifact"
                        )

        reporting_report = gate_reports.get("reporting_layers_current")
        if reporting_report:
            reported_ids = reporting_report.get("layer_ids")
            if (
                not isinstance(reported_ids, list)
                or not all(isinstance(value, str) for value in reported_ids)
                or len(reported_ids) != len(set(reported_ids))
                or set(reported_ids) != layer_ids
            ):
                errors.append(
                    "gates.reporting_layers_current artifact.layer_ids must match "
                    "declared reporting_layers"
                )
            for field in (
                "raw_result_hashes_verified",
                "publisher_manifests_current",
                "allowlisted_outputs_only",
            ):
                if reporting_report.get(field) is not True:
                    errors.append(
                        f"gates.reporting_layers_current artifact.{field} must be true"
                    )

        special = {
            "connectivity_review",
            "schema_ledger_validation",
            "baseline_comparison",
            "stock_resource_account_checks",
            "no_forcing_audit",
        }
        for name, report in gate_reports.items():
            if name in special:
                continue
            if report.get("case") != case_data.get("candidate_case"):
                errors.append(
                    f"gates.{name} artifact case does not match candidate_case"
                )
            if report.get("scenario") != case_data.get("scenario"):
                errors.append(f"gates.{name} artifact scenario does not match case")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument(
        "--stage",
        choices=("design", "source-input-patch", "pre-solve", "promotion"),
        default="design",
    )
    parser.add_argument(
        "--case-dir",
        type=Path,
        help="case root; defaults to PACKAGE's parent, or its parent when PACKAGE is in documentation/",
    )
    args = parser.parse_args()
    try:
        package = json.loads(args.package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    package_dir = args.package.resolve().parent
    inferred_case_dir = (
        package_dir.parent if package_dir.name == "documentation" else package_dir
    )
    errors = validate_package(
        package, args.stage, package_dir, args.case_dir or inferred_case_dir
    )
    if errors:
        print("calibration package: FAIL", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"calibration package: PASS (stage={args.stage})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
