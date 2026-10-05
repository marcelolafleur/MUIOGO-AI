"""Tests for the calibration-specific non-forcing audit."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("audit_no_forcing.py")
SPEC = importlib.util.spec_from_file_location("audit_no_forcing", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(AUDIT)


class NonForcingAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "genData.json").write_text(
            '{"osy-years": ["2020", "2025"]}\n', encoding="utf-8"
        )
        self.ledger = self.root / "ledger"
        self.ledger.mkdir()
        (self.ledger / "SOURCES.csv").write_text(
            "source_id\nSRC_STOCK\nSRC_BENCHMARK\n", encoding="utf-8"
        )
        (self.ledger / "CALCULATIONS.csv").write_text(
            "calculation_id,source_ids,assumption_ids,input_calculation_ids\n"
            "CALC_STOCK,SRC_BENCHMARK,,\n",
            encoding="utf-8",
        )
        (self.ledger / "ASSUMPTIONS.csv").write_text(
            "assumption_id,evidence_source_ids\n", encoding="utf-8"
        )
        self.package = {
            "changes": [],
            "benchmarks": [],
            "non_forcing": {"candidate_dispositions": []},
            "runtime": {},
        }

    def write_bounds(self, lower: float, upper: float) -> None:
        (self.root / "RYT.json").write_text(
            (
                '{"TAMinC":{"SC_0":[{"TechId":"TEC_A","2020":%s}]},'
                '"TAMaxC":{"SC_0":[{"TechId":"TEC_A","2020":%s}]}}\n'
            )
            % (lower, upper),
            encoding="utf-8",
        )

    def test_positive_pair_requires_physical_disposition(self) -> None:
        self.write_bounds(5, 5)
        report = AUDIT.audit(self.root, self.package, self.ledger)
        self.assertEqual(report["status"], "fail")
        candidate_id = report["candidates"][0]["candidate_id"]
        self.package["non_forcing"]["candidate_dispositions"] = [
            {
                "candidate_id": candidate_id,
                "status": "allowed_physical_input",
                "reason": "Sourced base-year stock",
                "evidence_ids": ["SRC_STOCK"],
            }
        ]
        self.assertEqual(
            AUDIT.audit(self.root, self.package, self.ledger)["status"], "pass"
        )

    def test_zero_upper_is_detected_without_a_lower_pair(self) -> None:
        self.write_bounds(-1, 0)
        report = AUDIT.audit(self.root, self.package, self.ledger)
        self.assertEqual(report["candidates"][0]["candidate_type"], "zero_upper_bound")

    def test_benchmark_overlap_and_sweep_are_nonwaivable(self) -> None:
        self.write_bounds(-1, -1)
        self.package.update(
            {
                "changes": [
                    {
                        "change_id": "CHG_A",
                        "evidence_ids": ["CALC_STOCK"],
                        "benchmark_source_exceptions": [],
                    }
                ],
                "benchmarks": [{"source_ids": ["SRC_BENCHMARK"]}],
                "runtime": {
                    "solve_attempts": [{"purpose": "sensitivity sweep for best fit"}]
                },
            }
        )
        report = AUDIT.audit(self.root, self.package, self.ledger)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(len(report["benchmark_lineage_failures"]), 1)
        self.assertEqual(len(report["prohibited_solve_attempts"]), 1)


if __name__ == "__main__":
    unittest.main()
