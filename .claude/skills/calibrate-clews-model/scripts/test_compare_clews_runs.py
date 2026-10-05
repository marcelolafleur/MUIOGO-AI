"""Tests for result-directory comparison."""

from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("compare_clews_runs.py")
SPEC = importlib.util.spec_from_file_location("compare_clews_runs", SCRIPT)
COMPARE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(COMPARE)


class CompareRunsTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.before, self.after = self.root / "before", self.root / "after"
        self.before.mkdir()
        self.after.mkdir()

    def write(
        self, directory: Path, name: str, values: list[tuple[str, float]]
    ) -> None:
        with (directory / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["t", "y", "value"])
            for technology, value in values:
                writer.writerow([technology, "2020", value])

    def test_structural_and_dispatch_are_separated(self) -> None:
        self.write(self.before, "Demand.csv", [("D", 10)])
        self.write(self.after, "Demand.csv", [("D", 10)])
        self.write(self.before, "RateOfActivity.csv", [("A", 4), ("B", 6)])
        self.write(self.after, "RateOfActivity.csv", [("A", 6), ("B", 4)])
        report = COMPARE.compare(self.before, self.after, 1e-9)
        self.assertEqual(report["structural_summary"]["Demand.csv"], "unchanged")
        self.assertEqual(report["classification"], COMPARE.ALTERNATE_OPTIMUM)
        activity = next(
            item for item in report["files"] if item["file"] == "RateOfActivity.csv"
        )
        self.assertEqual(activity["status"], "changed")
        self.assertEqual(activity["total_change"], 0)
        self.assertEqual(activity["affected"]["technologies"], ["A", "B"])
        self.assertEqual(activity["affected"]["years"], ["2020"])

    def test_reports_tables_present_on_only_one_side(self) -> None:
        self.write(self.before, "Demand.csv", [("D", 10)])
        self.write(self.after, "NewCapacity.csv", [("N", 2)])
        report = COMPARE.compare(self.before, self.after, 1e-9)
        self.assertEqual(report["baseline_only"], ["Demand.csv"])
        self.assertEqual(report["candidate_only"], ["NewCapacity.csv"])
        self.assertEqual(report["structural_summary"]["Demand.csv"], "baseline_only")
        self.assertEqual(
            report["structural_summary"]["NewCapacity.csv"], "candidate_only"
        )

    def test_structural_option_replaces_defaults(self) -> None:
        self.write(self.before, "CustomAccount.csv", [("A", 1)])
        self.write(self.after, "CustomAccount.csv", [("A", 2)])
        report = COMPARE.compare(self.before, self.after, 1e-9, {"CustomAccount.csv"})
        self.assertEqual(report["structural_summary"], {"CustomAccount.csv": "changed"})

    def test_exact_retired_identifiers_are_filtered(self) -> None:
        self.write(self.before, "Demand.csv", [("OLD", 1), ("KEEP", 10)])
        self.write(self.after, "Demand.csv", [("KEEP", 10)])
        report = COMPARE.compare(self.before, self.after, 1e-9, retired_values={"OLD"})
        self.assertEqual(report["classification"], COMPARE.EXACT_PARITY)
        demand = report["files"][0]
        self.assertEqual(demand["filtered_rows"], {"baseline": 1, "candidate": 0})

    def test_retirement_filter_does_not_match_substrings(self) -> None:
        self.write(self.before, "Demand.csv", [("OLD_X", 1), ("KEEP", 10)])
        self.write(self.after, "Demand.csv", [("KEEP", 10)])
        report = COMPARE.compare(self.before, self.after, 1e-9, retired_values={"OLD"})
        self.assertEqual(report["classification"], COMPARE.MATERIAL_CHANGE)

    def test_equivalent_routes_are_aggregated_explicitly(self) -> None:
        self.write(self.before, "Demand.csv", [("A", 4), ("B", 6)])
        self.write(self.after, "Demand.csv", [("A", 6), ("B", 4)])
        report = COMPARE.compare(
            self.before,
            self.after,
            1e-9,
            equivalence_groups={"t": {"A": "SERVICE", "B": "SERVICE"}},
        )
        self.assertEqual(report["classification"], COMPARE.ALTERNATE_OPTIMUM)
        demand = report["files"][0]
        self.assertEqual(demand["status"], "changed")
        self.assertEqual(demand["aggregate_status"], "unchanged")

    def test_core_annual_change_is_material(self) -> None:
        self.write(self.before, "Demand.csv", [("D", 10)])
        self.write(self.after, "Demand.csv", [("D", 11)])
        report = COMPARE.compare(self.before, self.after, 1e-9)
        self.assertEqual(report["classification"], COMPARE.MATERIAL_CHANGE)

    def test_schema_mismatch_fails_the_comparison(self) -> None:
        self.write(self.before, "Demand.csv", [("D", 10)])
        (self.after / "Demand.csv").write_text("f,value\nD,10\n", encoding="utf-8")
        report = COMPARE.compare(self.before, self.after, 1e-9)
        self.assertEqual(report["status"], "fail")


if __name__ == "__main__":
    unittest.main()
