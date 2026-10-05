"""Tests for the evidence-driven calibration-package validator."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate_calibration_package.py")
SPEC = importlib.util.spec_from_file_location("validate_calibration_package", SCRIPT)
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VALIDATOR)
TEMPLATE = Path(__file__).parents[1] / "assets" / "calibration-package.template.json"


class CalibrationPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.package = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write_ledgers(self) -> None:
        contents = {
            "SOURCES.csv": (
                "source_id,exact_locator\n"
                "SRC_COUNTRY_PLANT_REGISTER,table 1\n"
                "SRC_COUNTRY_GENERATION,table 2\n"
                "SRC_CONNECTIVITY,table 3\n"
            ),
            "CALCULATIONS.csv": (
                "calculation_id,source_ids,assumption_ids,input_calculation_ids\n"
                "CALC_EXISTING_STOCK_SURVIVAL,SRC_COUNTRY_PLANT_REGISTER,,\n"
            ),
            "ASSUMPTIONS.csv": (
                "assumption_id,evidence_source_ids\nASM_CONNECTIVITY,SRC_CONNECTIVITY\n"
            ),
            "MODEL_MAP.csv": (
                "map_id,model_file,parameter,superseded_by\n"
                "MAP_EXISTING_STOCK,RYT.json,ResidualCapacity,\n"
            ),
            "GAPS.csv": "item\nGAP_EXAMPLE\n",
            "CHANGES.csv": "change_id\nCHG_EXISTING_STOCK\n",
        }
        for relative in ("data_sources", "predecessor/data_sources"):
            directory = self.root / relative
            (directory / "evidence").mkdir(parents=True)
            (directory / "evidence/source.txt").write_text(
                "retained evidence\n", encoding="utf-8"
            )
            for filename, content in contents.items():
                (directory / filename).write_text(content, encoding="utf-8")

    def ready(self, stage: str) -> dict[str, object]:
        package = copy.deepcopy(self.package)
        package["provenance"]["predecessor_ledger_dir"] = "predecessor/data_sources"
        package["case"]["source_json_dir"] = "source_json"
        package["case"]["candidate_json_dir"] = "candidate_json"
        (self.root / "source_json").mkdir()
        (self.root / "candidate_json").mkdir()
        (self.root / "source_json/RYT.json").write_text("{}\n", encoding="utf-8")
        (self.root / "candidate_json/RYT.json").write_text(
            '{"changed": true}\n', encoding="utf-8"
        )
        self.write_ledgers()
        documentation = self.root / "documentation"
        documentation.mkdir()
        (documentation / "calibration-backlog.csv").write_text(
            "item_id,status\nX,resolved\n", encoding="utf-8"
        )
        (documentation / "HISTORY.md").write_text(
            "# History\n\nSource inputs updated.\n", encoding="utf-8"
        )
        (documentation / "connectivity-rules.json").write_text("{}\n", encoding="utf-8")

        def pass_gate(name: str, report: dict[str, object]) -> None:
            artifact = documentation / f"{name}.json"
            artifact.write_text(json.dumps(report), encoding="utf-8")
            package["gates"][name] = {
                "status": "passed",
                "artifact": str(artifact.relative_to(self.root)),
            }

        names = VALIDATOR.PRE_SOLVE_GATES
        if stage == "source-input-patch":
            names = VALIDATOR.SOURCE_INPUT_PATCH_GATES
            package["delivery"]["state"] = "source_input_patch"
            package["delivery"]["result_status"] = "stale"
        elif stage == "promotion":
            names = VALIDATOR.PROMOTION_GATES
            package["delivery"]["state"] = "promoted"
            package["delivery"]["result_status"] = "fresh"
        generic = {
            "status": "pass",
            "case": package["case"]["candidate_case"],
            "scenario": package["case"]["scenario"],
        }
        for name in names:
            pass_gate(name, generic)
        package["gates"]["stock_resource_account_checks"] = {
            "status": "not_applicable",
            "artifact": None,
            "reason": "Synthetic package has no closed resource account",
        }
        if stage != "source-input-patch":
            pass_gate(
                "connectivity_review",
                {
                    "schema": "clews-connectivity-audit-v1",
                    "status": "pass",
                    "case_dir": str(self.root),
                    "scenario": package["case"]["scenario"],
                    "findings": [],
                    "reviewed_exemptions": [],
                    "rule_errors": [],
                    "unused_exemptions": [],
                },
            )
            pass_gate(
                "no_forcing_audit",
                {
                    "schema": "clews-non-forcing-audit-v1",
                    "status": "pass",
                    "case_dir": str(self.root),
                    "unresolved_candidates": [],
                    "invalid_dispositions": [],
                    "prohibited_solve_attempts": [],
                    "benchmark_lineage_failures": [],
                },
            )
        pass_gate(
            "schema_ledger_validation",
            {
                "status": "pass",
                "stage": "delivery" if stage == "promotion" else "build",
                "ledger_dir": str(self.root / "data_sources"),
                "model_inputs": {"uncovered_inputs": []},
            },
        )
        if stage == "promotion":
            pass_gate(
                "baseline_comparison",
                {
                    "schema": "clews-run-comparison-v2",
                    "status": "pass",
                    "classification": "EXACT_PARITY",
                    "strict_row_parity": True,
                    "structural_parity": True,
                    "common_file_count": 1,
                    "baseline_only": [],
                    "candidate_only": [],
                },
            )
        return package

    def validate(self, package: dict[str, object], stage: str) -> list[str]:
        return VALIDATOR.validate_package(
            package, stage, self.root / "documentation", self.root
        )

    def test_template_passes_design(self) -> None:
        self.assertEqual(VALIDATOR.validate_package(self.package, "design"), [])

    def test_package_scope_fields_are_required(self) -> None:
        package = copy.deepcopy(self.package)
        package["packages"][0]["coherence_basis"] = ""
        package["packages"][0]["temporal_boundary"]["latest_evidence_year"] = "2024"
        package["packages"][0]["evidence_boundary"]["allocation_rule"] = ""
        package["packages"][0]["claim_scope"] = ""
        package["packages"][0]["invariants"] = []
        errors = VALIDATOR.validate_package(package, "design")
        self.assertTrue(any("coherence_basis" in error for error in errors))
        self.assertTrue(any("latest_evidence_year" in error for error in errors))
        self.assertTrue(any("allocation_rule" in error for error in errors))
        self.assertTrue(any("claim_scope" in error for error in errors))
        self.assertTrue(
            any("invariants must be a non-empty list" in error for error in errors)
        )

    def test_invariant_names_must_be_unique(self) -> None:
        package = copy.deepcopy(self.package)
        package["packages"][0]["invariants"].append(
            copy.deepcopy(package["packages"][0]["invariants"][0])
        )
        errors = VALIDATOR.validate_package(package, "design")
        self.assertTrue(any(".name duplicates" in error for error in errors))

    def test_complete_package_passes_promotion(self) -> None:
        self.assertEqual(self.validate(self.ready("promotion"), "promotion"), [])

    def test_postprocessed_layer_requires_current_publication_report(self) -> None:
        package = self.ready("promotion")
        package["reporting_layers"] = [
            {
                "layer_id": "ENV_WATER_PIVOT",
                "purpose": "Publish authoritative water accounting in Pivot",
                "type": "postprocessed",
                "publisher_script": "scripts/publish_water.py",
                "publisher_version": "v1",
                "raw_inputs": ["res/BASE/RateOfActivity.csv"],
                "published_outputs": ["view/RYTM.json"],
                "manifest": "documentation/water-publication.json",
                "rerun_after_every_solve": True,
            }
        ]
        package["gates"]["reporting_layers_current"] = {
            "status": "not_applicable",
            "artifact": None,
            "reason": "incorrectly skipped",
        }
        errors = self.validate(package, "promotion")
        self.assertTrue(any("mandatory and cannot" in error for error in errors))

        artifact = self.root / "documentation/reporting_layers_current.json"
        artifact.write_text(
            json.dumps(
                {
                    "schema": "clews-reporting-layer-validation-v1",
                    "status": "pass",
                    "case": package["case"]["candidate_case"],
                    "scenario": package["case"]["scenario"],
                    "layer_ids": ["ENV_WATER_PIVOT"],
                    "raw_result_hashes_verified": True,
                    "publisher_manifests_current": True,
                    "allowlisted_outputs_only": True,
                }
            ),
            encoding="utf-8",
        )
        package["gates"]["reporting_layers_current"] = {
            "status": "passed",
            "artifact": "documentation/reporting_layers_current.json",
        }
        self.assertEqual(self.validate(package, "promotion"), [])

    def test_alternate_optimum_requires_explicit_promotion_decision(self) -> None:
        package = self.ready("promotion")
        relative = package["gates"]["baseline_comparison"]["artifact"]
        artifact = self.root / relative
        report = json.loads(artifact.read_text(encoding="utf-8"))
        report.update(
            {
                "classification": "STRUCTURAL_PARITY_ALTERNATE_OPTIMUM_CANDIDATE",
                "strict_row_parity": False,
                "structural_parity": True,
            }
        )
        artifact.write_text(json.dumps(report), encoding="utf-8")
        errors = self.validate(package, "promotion")
        self.assertTrue(any("explicitly accept" in error for error in errors))
        package["delivery"]["alternate_optimum_decision"] = {
            "accepted": True,
            "rationale": "Core annual outcomes are invariant; only equivalent dispatch rows moved.",
            "comparison_artifact": relative,
        }
        self.assertEqual(self.validate(package, "promotion"), [])

    def test_retirement_requires_declared_objects_and_evidence_artifacts(self) -> None:
        package = self.ready("pre-solve")
        change = package["changes"][0]
        change["change_type"] = "object_retirement"
        errors = self.validate(package, "pre-solve")
        self.assertTrue(any("retired_object_ids" in error for error in errors))
        self.assertTrue(
            any("reference_inventory_artifact" in error for error in errors)
        )
        self.assertTrue(
            any("inactivity_evidence_artifact" in error for error in errors)
        )

        for name in ("reference-inventory.json", "inactivity-evidence.json"):
            (self.root / "documentation" / name).write_text("{}\n", encoding="utf-8")
        change.update(
            {
                "retired_object_ids": ["TEC_OLD", "COM_OLD"],
                "reference_inventory_artifact": "documentation/reference-inventory.json",
                "inactivity_evidence_artifact": "documentation/inactivity-evidence.json",
            }
        )
        self.assertEqual(self.validate(package, "pre-solve"), [])

    def test_source_input_patch_passes_without_solver_gates(self) -> None:
        package = self.ready("source-input-patch")
        self.assertEqual(package["gates"]["solver_run"]["status"], "pending")
        self.assertEqual(self.validate(package, "source-input-patch"), [])

    def test_source_input_patch_requires_truthful_delivery_state(self) -> None:
        package = self.ready("source-input-patch")
        package["delivery"]["state"] = "working"
        package["delivery"]["result_status"] = "fresh"
        package["delivery"]["recertification_command"] = ""
        (self.root / "documentation/HISTORY.md").unlink()
        errors = self.validate(package, "source-input-patch")
        self.assertTrue(any("must equal source_input_patch" in e for e in errors))
        self.assertTrue(any("must be absent or stale" in e for e in errors))
        self.assertTrue(any("recertification_command" in e for e in errors))
        self.assertTrue(any("history_artifact does not exist" in e for e in errors))

    def test_pre_solve_checks_inherited_records(self) -> None:
        package = self.ready("pre-solve")
        (self.root / "data_sources/SOURCES.csv").write_text(
            "source_id\nSRC_COUNTRY_GENERATION\nSRC_CONNECTIVITY\n", encoding="utf-8"
        )
        errors = self.validate(package, "pre-solve")
        self.assertTrue(any("inheritance dropped SOURCES.csv" in e for e in errors))

    def test_fabricated_lineage_fails(self) -> None:
        package = self.ready("promotion")
        package["changes"][0]["evidence_ids"] = ["SRC_DOES_NOT_EXIST"]
        package["changes"][0]["model_map_ids"] = ["MAP_DOES_NOT_EXIST"]
        errors = self.validate(package, "promotion")
        self.assertTrue(any("SRC_DOES_NOT_EXIST" in e for e in errors))
        self.assertTrue(any("MAP_DOES_NOT_EXIST" in e for e in errors))

    def test_connectivity_finding_requires_disposition(self) -> None:
        package = self.ready("pre-solve")
        artifact = self.root / package["gates"]["connectivity_review"]["artifact"]
        report = json.loads(artifact.read_text(encoding="utf-8"))
        report["status"] = "findings"
        report["findings"] = [{"finding_id": "required_link_missing:RULE:USE:1"}]
        artifact.write_text(json.dumps(report), encoding="utf-8")
        package["packages"][0]["connectivity_finding_ids"] = [
            "required_link_missing:RULE:USE:1"
        ]
        errors = self.validate(package, "pre-solve")
        self.assertTrue(any("has no disposition" in e for e in errors))

    def test_promotion_requires_disposition_evidence(self) -> None:
        package = self.ready("promotion")
        finding_id = "required_link_missing:RULE:USE:1"
        artifact = self.root / package["gates"]["connectivity_review"]["artifact"]
        report = json.loads(artifact.read_text(encoding="utf-8"))
        report["status"] = "findings"
        report["findings"] = [{"finding_id": finding_id}]
        artifact.write_text(json.dumps(report), encoding="utf-8")
        package["packages"][0]["connectivity_finding_ids"] = [finding_id]
        package["connectivity"]["finding_dispositions"] = [
            {
                "finding_id": finding_id,
                "status": "resolved",
                "resolution": "fixed",
                "evidence_ids": [],
            }
        ]
        errors = self.validate(package, "promotion")
        self.assertTrue(any("evidence_ids are required" in e for e in errors))

    def test_placeholder_gate_artifact_fails(self) -> None:
        package = self.ready("pre-solve")
        artifact = self.root / package["gates"]["identifier_integrity"]["artifact"]
        artifact.write_text("placeholder\n", encoding="utf-8")
        errors = self.validate(package, "pre-solve")
        self.assertTrue(any("not readable JSON" in e for e in errors))

    def test_not_applicable_requires_reason_and_is_restricted(self) -> None:
        package = self.ready("pre-solve")
        package["gates"]["identifier_integrity"] = {
            "status": "not_applicable",
            "artifact": None,
        }
        errors = self.validate(package, "pre-solve")
        self.assertTrue(any("reason must be non-empty" in e for e in errors))
        self.assertTrue(any("mandatory and cannot" in e for e in errors))

    def test_source_diff_is_checked_against_real_files(self) -> None:
        package = self.ready("pre-solve")
        (self.root / "candidate_json/OTHER.json").write_text("{}\n", encoding="utf-8")
        errors = self.validate(package, "pre-solve")
        self.assertTrue(any("actual changed source JSON" in e for e in errors))

    def test_formatting_only_json_churn_is_ignored(self) -> None:
        package = self.ready("pre-solve")
        (self.root / "source_json/OTHER.json").write_text(
            '{"a":1,"b":2}\n', encoding="utf-8"
        )
        (self.root / "candidate_json/OTHER.json").write_text(
            '{\n  "b": 2,\n  "a": 1\n}\n', encoding="utf-8"
        )
        self.assertEqual(self.validate(package, "pre-solve"), [])

    def test_regeneration_change_requires_matching_hashes(self) -> None:
        package = self.ready("pre-solve")
        before = self.root / "source_json/OTHER.json"
        after = self.root / "candidate_json/OTHER.json"
        before.write_text('{"metadata":"old"}\n', encoding="utf-8")
        after.write_text('{"metadata":"new"}\n', encoding="utf-8")
        package["regeneration_changes"] = [
            {
                "source_file": "OTHER.json",
                "before_sha256": hashlib.sha256(before.read_bytes()).hexdigest(),
                "after_sha256": hashlib.sha256(after.read_bytes()).hexdigest(),
                "classification": "metadata_only",
                "reason": "UpdateCase refreshes its version marker",
            }
        ]
        self.assertEqual(self.validate(package, "pre-solve"), [])

    def test_resolved_and_reviewed_exemption_dispositions_are_retained(self) -> None:
        package = self.ready("promotion")
        package["connectivity"]["finding_dispositions"] = [
            {
                "finding_id": "old:finding",
                "status": "resolved",
                "resolution": "Route connected in this wave",
                "evidence_ids": ["SRC_CONNECTIVITY"],
                "gap_items": [],
            },
            {
                "finding_id": "reviewed:exemption",
                "status": "exempted",
                "resolution": "Legitimate sourced boundary",
                "evidence_ids": ["SRC_CONNECTIVITY"],
                "gap_items": [],
            },
        ]
        artifact = self.root / package["gates"]["connectivity_review"]["artifact"]
        report = json.loads(artifact.read_text(encoding="utf-8"))
        report["reviewed_exemptions"] = [{"finding_id": "reviewed:exemption"}]
        artifact.write_text(json.dumps(report), encoding="utf-8")
        self.assertEqual(self.validate(package, "promotion"), [])

    def test_deferred_finding_cites_gap_not_evidence(self) -> None:
        package = self.ready("promotion")
        finding_id = "required_link_missing:RULE:USE:1"
        artifact = self.root / package["gates"]["connectivity_review"]["artifact"]
        report = json.loads(artifact.read_text(encoding="utf-8"))
        report["status"] = "findings"
        report["findings"] = [{"finding_id": finding_id}]
        artifact.write_text(json.dumps(report), encoding="utf-8")
        package["packages"][0]["connectivity_finding_ids"] = [finding_id]
        package["connectivity"]["finding_dispositions"] = [
            {
                "finding_id": finding_id,
                "status": "deferred",
                "resolution": "National routing evidence is not yet available",
                "evidence_ids": [],
                "gap_items": ["GAP_EXAMPLE"],
            }
        ]
        self.assertEqual(self.validate(package, "promotion"), [])

    def test_audited_source_locator_correction_is_allowed(self) -> None:
        package = self.ready("pre-solve")
        source = self.root / "data_sources/SOURCES.csv"
        source.write_text(
            source.read_text(encoding="utf-8").replace("table 1", "table 1 page 7"),
            encoding="utf-8",
        )
        artifact = self.root / "documentation/source-correction.md"
        artifact.write_text("Verified against the retained source.\n", encoding="utf-8")
        package["provenance"]["corrections"] = [
            {
                "table": "SOURCES.csv",
                "id": "SRC_COUNTRY_PLANT_REGISTER",
                "field": "exact_locator",
                "before": "table 1",
                "after": "table 1 page 7",
                "reason": "Correct the inherited page locator",
                "evidence_artifact": "documentation/source-correction.md",
            }
        ]
        self.assertEqual(self.validate(package, "pre-solve"), [])

    def test_benchmark_overlap_is_transitive_and_requires_reason(self) -> None:
        package = self.ready("pre-solve")
        content = (
            "calculation_id,source_ids,assumption_ids,input_calculation_ids\n"
            "CALC_EXISTING_STOCK_SURVIVAL,SRC_COUNTRY_GENERATION,,\n"
        )
        for path in (
            self.root / "data_sources/CALCULATIONS.csv",
            self.root / "predecessor/data_sources/CALCULATIONS.csv",
        ):
            path.write_text(content, encoding="utf-8")
        errors = self.validate(package, "pre-solve")
        self.assertTrue(any("diagnostic benchmark sources" in e for e in errors))
        package["changes"][0]["benchmark_source_exceptions"] = [
            {
                "source_id": "SRC_COUNTRY_GENERATION",
                "reason": "The cited table independently measures the physical initial stock",
            }
        ]
        self.assertEqual(self.validate(package, "pre-solve"), [])

    def test_inherited_coverage_gap_can_continue_but_not_promote(self) -> None:
        package = self.ready("pre-solve")
        artifact = self.root / package["gates"]["schema_ledger_validation"]["artifact"]
        report = json.loads(artifact.read_text(encoding="utf-8"))
        report["model_inputs"] = {
            "uncovered_inputs": ["Legacy.csv"],
            "uncovered_required_inputs": [],
            "legacy_uncovered_inputs": ["Legacy.csv"],
        }
        artifact.write_text(json.dumps(report), encoding="utf-8")
        package["provenance"]["inherited_coverage_gaps"] = [
            {
                "model_file": "Legacy.csv",
                "reason": "Untouched inherited input",
                "backlog_item": "X",
            }
        ]
        self.assertEqual(self.validate(package, "pre-solve"), [])

    def test_inherited_coverage_gap_blocks_promotion(self) -> None:
        package = self.ready("promotion")
        artifact = self.root / package["gates"]["schema_ledger_validation"]["artifact"]
        report = json.loads(artifact.read_text(encoding="utf-8"))
        report["model_inputs"] = {
            "uncovered_inputs": ["Legacy.csv"],
            "uncovered_required_inputs": [],
            "legacy_uncovered_inputs": ["Legacy.csv"],
        }
        artifact.write_text(json.dumps(report), encoding="utf-8")
        package["provenance"]["inherited_coverage_gaps"] = [
            {
                "model_file": "Legacy.csv",
                "reason": "Untouched inherited input",
                "backlog_item": "X",
            }
        ]
        errors = self.validate(package, "promotion")
        self.assertTrue(any("promotion requires complete" in e for e in errors))

    def test_repair_solve_limit_requires_explicit_authorization(self) -> None:
        package = copy.deepcopy(self.package)
        package["runtime"]["repair_solves_used"] = 4
        errors = VALIDATOR.validate_package(package, "design")
        self.assertTrue(any("additional_solve_authorization" in e for e in errors))
        package["runtime"]["additional_solve_authorization"] = "User requested one more solve"
        self.assertEqual(VALIDATOR.validate_package(package, "design"), [])

    def test_cli_infers_case_root_for_documentation_package(self) -> None:
        package = self.ready("pre-solve")
        package_path = self.root / "documentation/calibration-package.json"
        package_path.write_text(json.dumps(package), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPT),
                str(package_path),
                "--stage",
                "pre-solve",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
