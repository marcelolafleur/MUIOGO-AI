"""Tests for closed-resource-account validation."""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate_resource_account.py")
SPEC = importlib.util.spec_from_file_location("validate_resource_account", SCRIPT)
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VALIDATOR)
TEMPLATE = Path(__file__).parents[1] / "assets" / "resource-account.template.json"


class ResourceAccountTest(unittest.TestCase):
    def setUp(self) -> None:
        self.account = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    def test_template_passes(self) -> None:
        self.assertEqual(VALIDATOR.validate_account(self.account), [])

    def test_ledger_references_are_resolved(self) -> None:
        ledger = {
            "sources": {"SRC_ACCOUNT_STOCK", "SRC_TRANSITION_RATE"},
            "calculations": {"CALC_ACCOUNT_RECONCILIATION"},
            "assumptions": set(),
        }
        self.assertEqual(VALIDATOR.validate_account(self.account, ledger), [])
        self.account["transitions"][0]["evidence_ids"] = ["SRC_MISSING"]
        errors = VALIDATOR.validate_account(self.account, ledger)
        self.assertTrue(any("SRC_MISSING" in error for error in errors))

    def test_missing_land_is_detected(self) -> None:
        account = copy.deepcopy(self.account)
        account["total"]["2021"] = 120
        errors = VALIDATOR.validate_account(account)
        self.assertTrue(any("ceilings is below total" in error for error in errors))

    def test_base_year_floor_is_not_initialization(self) -> None:
        account = copy.deepcopy(self.account)
        account["classes"][0]["upper"]["2020"] = 100
        errors = VALIDATOR.validate_account(account)
        self.assertTrue(
            any("base year is not initialized" in error for error in errors)
        )

    def test_cumulative_envelope_cannot_claim_annual_maximum(self) -> None:
        account = copy.deepcopy(self.account)
        account["transitions"][0]["implementation"] = "cumulative_envelope"
        errors = VALIDATOR.validate_account(account)
        self.assertTrue(any("claims an annual maximum" in error for error in errors))

    def test_cluster_scope_requires_allocation_evidence(self) -> None:
        account = copy.deepcopy(self.account)
        account["index_scope"]["constraint_scope"] = "cluster"
        errors = VALIDATOR.validate_account(account)
        self.assertTrue(any("allocation_evidence_ids" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
