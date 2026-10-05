"""Tests for staged provenance coverage during calibration work."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("provenance.py")
SPEC = importlib.util.spec_from_file_location("calibration_provenance", SCRIPT)
PROVENANCE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PROVENANCE)


class ProvenanceCoverageTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        for name in ("Touched.csv", "Legacy.csv"):
            (self.inputs / name).write_text("VALUE\n1\n", encoding="utf-8")

    def validator(self, required: list[str], allow: bool, mapped: str):
        validator = PROVENANCE.LedgerValidator(
            self.root,
            "build",
            self.inputs,
            required,
            allow,
        )
        validator.rows["MODEL_MAP.csv"] = [
            {"model_file": mapped, "superseded_by": ""}
        ]
        validator.check_coverage()
        return validator

    def test_inherited_gap_warns_while_touched_input_remains_strict(self) -> None:
        validator = self.validator(["Touched.csv"], True, "Touched.csv")
        self.assertEqual(validator.failures, [])
        self.assertEqual(validator.coverage["legacy_uncovered_inputs"], ["Legacy.csv"])
        self.assertTrue(validator.warnings)

    def test_uncovered_touched_input_fails(self) -> None:
        validator = self.validator(["Touched.csv"], True, "Legacy.csv")
        self.assertTrue(any("touched model inputs" in item for item in validator.failures))

    def test_delivery_does_not_waive_inherited_gap(self) -> None:
        validator = PROVENANCE.LedgerValidator(
            self.root,
            "delivery",
            self.inputs,
            ["Touched.csv"],
            True,
        )
        validator.rows["MODEL_MAP.csv"] = [
            {"model_file": "Touched.csv", "superseded_by": ""}
        ]
        validator.check_coverage()
        self.assertTrue(any("inherited untouched" in item for item in validator.failures))


if __name__ == "__main__":
    unittest.main()
