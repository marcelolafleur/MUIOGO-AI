"""Synthetic regression tests for the MUIO connectivity audit."""

from __future__ import annotations

import importlib.util
import copy
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("audit_clews_connectivity.py")
SPEC = importlib.util.spec_from_file_location("audit_clews_connectivity", SCRIPT)
AUDITOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(AUDITOR)


class ConnectivityAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        gen = {
            "osy-years": ["2020"],
            "osy-scenarios": [{"ScenarioId": "SC_0", "Active": True}],
            "osy-tech": [
                {"TechId": "SUPPLY", "Tech": "Free supply"},
                {"TechId": "USE", "Tech": "Useful process"},
            ],
            "osy-comm": [
                {"CommId": "RESOURCE", "Comm": "Resource"},
                {"CommId": "SERVICE", "Comm": "Service"},
                {"CommId": "ORPHAN", "Comm": "Orphan"},
            ],
        }
        rytcm = {
            "IAR": {
                "SC_0": [{"TechId": "USE", "CommId": "RESOURCE", "MoId": 1, "2020": 1}]
            },
            "OAR": {
                "SC_0": [
                    {"TechId": "SUPPLY", "CommId": "RESOURCE", "MoId": 1, "2020": 1},
                    {"TechId": "USE", "CommId": "SERVICE", "MoId": 1, "2020": 1},
                ]
            },
        }
        ryt = {
            "TAU": {
                "SC_0": [
                    {"TechId": "SUPPLY", "2020": 999999},
                    {"TechId": "USE", "2020": 999999},
                ]
            },
            "CC": {"SC_0": []},
            "FC": {"SC_0": []},
            "TAMaxC": {"SC_0": []},
            "TAMaxCI": {"SC_0": []},
        }
        rytm = {
            "VC": {
                "SC_0": [
                    {"TechId": "SUPPLY", "MoId": 1, "2020": 0},
                    {"TechId": "USE", "MoId": 1, "2020": 1},
                ]
            },
            "TAMUL": {"SC_0": []},
        }
        for name, payload in (
            ("genData.json", gen),
            ("RYTCM.json", rytcm),
            ("RYT.json", ryt),
            ("RYTM.json", rytm),
        ):
            (self.root / name).write_text(json.dumps(payload), encoding="utf-8")
        self.rules = {
            "schema_version": 1,
            "scenario": "SC_0",
            "unbounded_threshold": 99990,
            "technology_roles": {},
            "terminal_commodity_ids": ["SERVICE"],
            "exogenous_commodity_ids": [],
            "required_links": [
                {
                    "rule_id": "USE_NEEDS_RESOURCE_AND_LAND",
                    "technology_ids": ["USE"],
                    "required_input_commodity_ids": ["RESOURCE", "LAND"],
                    "require_all": True,
                    "reason": "Test physical link",
                }
            ],
            "reviewed_exemptions": [],
        }

    def test_detects_unlimited_free_and_missing_link(self) -> None:
        report = AUDITOR.audit(self.root, self.rules)
        kinds = {item["finding_type"] for item in report["findings"]}
        self.assertIn("unlimited_free_output_candidate", kinds)
        self.assertIn("required_link_missing", kinds)
        self.assertIn("unused_commodity", kinds)

    def test_reviewed_exemption_is_separated(self) -> None:
        self.rules["technology_roles"] = {
            "SUPPLY": {"role": "resource_supply", "basis": "boundary"}
        }
        self.rules["reviewed_exemptions"] = [
            {
                "finding_id": "unlimited_free_output_candidate:SUPPLY:1",
                "reason": "Synthetic test exemption",
                "evidence_ids": ["ASM_TEST"],
            }
        ]
        report = AUDITOR.audit(self.root, self.rules)
        self.assertEqual(len(report["reviewed_exemptions"]), 1)
        self.assertNotIn(
            "SUPPLY:1",
            [
                item["entity_id"]
                for item in report["findings"]
                if item["finding_type"] == "unlimited_free_output_candidate"
            ],
        )

    def test_reviewed_exemption_evidence_must_resolve_when_ledger_is_given(self) -> None:
        self.rules["reviewed_exemptions"] = [
            {
                "finding_id": "inputless_output_mode:TEC_SUPPLY:1",
                "reason": "Sourced resource boundary",
                "evidence_ids": ["SRC_MISSING"],
            }
        ]
        report = AUDITOR.audit(self.root, self.rules, {"SRC_OTHER"})
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("SRC_MISSING" in error for error in report["rule_errors"]))

    def test_partial_horizon_bound_does_not_hide_free_route(self) -> None:
        gen = json.loads((self.root / "genData.json").read_text(encoding="utf-8"))
        gen["osy-years"] = ["2020", "2025", "2030"]
        (self.root / "genData.json").write_text(json.dumps(gen), encoding="utf-8")
        for filename in ("RYTCM.json", "RYT.json", "RYTM.json"):
            document = json.loads((self.root / filename).read_text(encoding="utf-8"))
            for parameter in document.values():
                for row in parameter["SC_0"]:
                    row["2025"] = row["2020"]
                    row["2030"] = row["2020"]
            (self.root / filename).write_text(json.dumps(document), encoding="utf-8")
        ryt = json.loads((self.root / "RYT.json").read_text(encoding="utf-8"))
        ryt["TAU"]["SC_0"][0].update({"2020": 10, "2025": -1, "2030": -1})
        (self.root / "RYT.json").write_text(json.dumps(ryt), encoding="utf-8")
        report = AUDITOR.audit(self.root, self.rules)
        finding = next(
            item
            for item in report["findings"]
            if item["finding_id"] == "unlimited_free_output_candidate:SUPPLY:1"
        )
        self.assertEqual(finding["detail"]["unlimited_free_years"], ["2025", "2030"])

    def test_unknown_rule_entities_and_stale_exemptions_fail_closed(self) -> None:
        self.rules["required_links"][0]["technology_ids"] = ["TYPO"]
        self.rules["reviewed_exemptions"] = [
            {
                "finding_id": "inputless_output_mode:NO_LONGER_PRESENT:1",
                "reason": "stale",
                "evidence_ids": ["ASM_TEST"],
            }
        ]
        report = AUDITOR.audit(self.root, self.rules)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(report["rule_errors"])
        self.assertTrue(report["unused_exemptions"])

    def test_required_link_finding_ids_include_rule_id(self) -> None:
        duplicate = copy.deepcopy(self.rules["required_links"][0])
        duplicate["rule_id"] = "SECOND_RULE"
        self.rules["required_links"].append(duplicate)
        report = AUDITOR.audit(self.root, self.rules)
        identifiers = {
            item["finding_id"]
            for item in report["findings"]
            if item["finding_type"] == "required_link_missing"
        }
        self.assertEqual(
            identifiers,
            {
                "required_link_missing:USE_NEEDS_RESOURCE_AND_LAND:USE:1",
                "required_link_missing:SECOND_RULE:USE:1",
            },
        )


if __name__ == "__main__":
    unittest.main()
