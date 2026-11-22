import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts/character-slots.py"
SPEC = importlib.util.spec_from_file_location("character_slots", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
WORLD = "CharactersPerRealm = 20\nCharactersPerAccount = 128\n"
COA = "CoA.CharacterSelectionEnable = 1\nCoA.CharacterSelectionMaxActive = 20\n"


class CharacterSlotsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = self.root / "worldserver.conf"
        self.coa = self.root / "coa.conf"
        self.world.write_text(WORLD)
        self.coa.write_text(COA)

    def audit(self):
        return MODULE.audit(self.world, self.coa)

    def test_reference_configuration_passes_without_writing_files(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in [self.world, self.coa]}
        result = self.audit()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["observed"], MODULE.EXPECTED)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})
        self.assertEqual(set(self.root.iterdir()), set(before))

    def test_old_advertised_ten_limit_fails(self):
        self.coa.write_text(COA.replace("= 20", "= 10"))
        result = self.audit()
        self.assertEqual(result["status"], "failed")
        self.assertIn("MaxActive is 10", " ".join(result["issues"]))

    def test_core_and_account_limits_cannot_silently_regress(self):
        for value in [WORLD.replace("= 20", "= 10"), WORLD.replace("= 128", "= 10")]:
            with self.subTest(value=value):
                self.world.write_text(value)
                self.assertEqual(self.audit()["status"], "failed")

    def test_disabled_metadata_fails(self):
        self.coa.write_text(COA.replace("Enable = 1", "Enable = 0"))
        self.assertEqual(self.audit()["status"], "failed")

    def test_missing_key_does_not_assume_a_default(self):
        self.coa.write_text("CoA.CharacterSelectionEnable = 1\n")
        self.assertEqual(self.audit()["status"], "failed")

    def test_duplicate_keys_across_files_require_review(self):
        self.world.write_text(WORLD + "CoA.CharacterSelectionMaxActive = 10\n")
        self.assertEqual(self.audit()["status"], "failed")
        self.world.write_text(WORLD + "CharactersPerRealm = 20\n")
        self.assertEqual(self.audit()["status"], "failed")

    def test_quoted_values_comments_bom_and_crlf(self):
        self.world.write_bytes(b'\xef\xbb\xbf# CharactersPerRealm = 10\r\nCharactersPerRealm = "20" # preserved\r\nCharactersPerAccount = 128\r\n')
        self.coa.write_text(COA + "\n# CoA.CharacterSelectionMaxActive = 10\n")
        self.assertEqual(self.audit()["status"], "passed")

    def test_invalid_and_partial_numbers_fail_without_echoing_values(self):
        for value in ["20oops", "20.0", '"20', "-1", "sensitive-value", "9" * 5000]:
            with self.subTest(value=value):
                self.world.write_text(WORLD.replace("= 20", "= " + value))
                result = self.audit()
                self.assertEqual(result["status"], "failed")
                self.assertNotIn(value, json.dumps(result["issues"]))

    def test_missing_or_same_file_is_unavailable(self):
        self.assertEqual(MODULE.audit(self.world, self.world)["status"], "unavailable")
        self.coa.unlink()
        self.assertEqual(self.audit()["status"], "unavailable")

    def test_cli_exit_codes_and_secret_omission(self):
        self.world.write_text(WORLD + 'WorldDatabaseInfo = "private-connection-secret"\n')
        for expected, content in [(0, COA), (2, COA.replace("= 20", "= 10")), (3, None)]:
            with self.subTest(expected=expected):
                if content is None:
                    self.coa.unlink()
                else:
                    self.coa.write_text(content)
                result = subprocess.run([sys.executable, "-B", str(TOOL), "audit", "--world-config", str(self.world), "--coa-config", str(self.coa)], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected)
                self.assertNotIn("private-connection-secret", result.stdout + result.stderr)
                self.assertIn("configuration-files-only", result.stdout)


if __name__ == "__main__":
    unittest.main()
