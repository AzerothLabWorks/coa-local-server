import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/client-patches.py"
SPEC = importlib.util.spec_from_file_location("client_repairs", SCRIPT)
REPAIR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPAIR)


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


class Patches(unittest.TestCase):
    def test_unsafe_paths(self):
        for name in ("../escape", "a/../b", "/root", "C:/root", "a\\b", "a//b", "a/./b",
                     "CON", "data/NUL.txt", "a.", "a ", "", "a\x00b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                REPAIR.relative(name)

    def test_safe_path(self):
        self.assertEqual(str(REPAIR.relative("Interface/AddOns/MyAddon/test.lua")),
                         "Interface/AddOns/MyAddon/test.lua")

    def test_multiple_files_and_hunks(self):
        data = ("diff --git a/a b/a\n--- a/a\n+++ b/a\n@@ -1,2 +1,2 @@\n x\n-old\n+new\n"
                "@@ -5 +5 @@\n-last\n+end\n"
                "diff --git a/b b/b\nindex 123..456 100644\n--- a/b\n+++ b/b\n"
                "@@ -1 +1 @@\n-before\n+after\n")
        self.assertEqual(REPAIR.patch_sections(data),
                         {"a": [("x\nold\n", "x\nnew\n"), ("last\n", "end\n")],
                          "b": [("before\n", "after\n")]})

    def test_wrong_hunk_count(self):
        with self.assertRaises(ValueError):
            REPAIR.patch_sections("--- a/a\n+++ b/a\n@@ -1,2 +1 @@\n-x\n+y\n")

    def test_rename_rejected(self):
        with self.assertRaises(ValueError):
            REPAIR.patch_sections("--- a/a\n+++ b/b\n@@ -1 +1 @@\n-x\n+y\n")

    def test_real_patch_structure(self):
        root = SCRIPT.parents[1] / "client-patches"
        expected = {"coa-native/native-talent-loaders.patch": 2,
                    "coa-cosmetics/native-appearance-vanity.patch": 3,
                    "coa-cosmetics/required-apply-argument.patch": 1,
                    "coa-range/WeakAuras-GetRange.patch": 1}
        for path, count in expected.items():
            with self.subTest(path=path):
                self.assertEqual(len(REPAIR.patch_sections((root / path).read_text())), count)

    def test_manifest_payloads_exist(self):
        manifest = REPAIR.read_json(REPAIR.MANIFEST)
        self.assertEqual(len(REPAIR.source_inventory(manifest)), 6)
        for member, item in manifest["members"].items():
            REPAIR.relative(member)
            self.assertRegex(item["after"], r"^[0-9a-f]{64}$")

    def test_transform_preserves_newlines(self):
        for newline in (b"\n", b"\r\n"):
            with self.subTest(newline=newline), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "test.patch").write_text("--- a/a\n+++ b/a\n@@ -1,2 +1,2 @@\n first\n-old\n+new\n")
                old, new = b"first" + newline + b"old" + newline, b"first" + newline + b"new" + newline
                item = {"before": [hash_bytes(old)], "after": hash_bytes(new), "patch": "test.patch"}
                with patch.object(REPAIR, "PATCHES", root):
                    self.assertEqual(REPAIR.transform(old, item, "a"), new)
                    self.assertEqual(REPAIR.transform(new, item, "a"), new)
                    with self.assertRaises(ValueError):
                        REPAIR.transform(b"unknown", item, "a")

    def test_wrong_patched_hash_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "x").write_bytes(b"new")
            item = {"before": [hash_bytes(b"old")], "after": hash_bytes(b"other"), "replacement": "x"}
            with patch.object(REPAIR, "PATCHES", root), self.assertRaises(ValueError):
                REPAIR.transform(b"old", item, "a")

    def test_removal_preserves_mixed_newlines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "x").write_text("--- a/a\n+++ b/a\n@@ -1,3 +1,2 @@\n first\n-old\n last\n")
            old, new = b"first\r\nold\nlast\r\n", b"first\r\nlast\r\n"
            item = {"before": [hash_bytes(old)], "after": hash_bytes(new), "patch": "x"}
            with patch.object(REPAIR, "PATCHES", root):
                self.assertEqual(REPAIR.transform(old, item, "a"), new)

    def test_running_client_rejected(self):
        result = subprocess.CompletedProcess([], 0, stdout='"Ascension.exe","123","Console","1","20 K"\n')
        with patch.object(REPAIR.os, "name", "nt"), patch.object(REPAIR.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(ValueError, "Fully close"):
                REPAIR.require_closed()

    def test_process_inventory_failure_rejected(self):
        with patch.object(REPAIR.os, "name", "nt"), patch.object(REPAIR.subprocess, "run",
                 side_effect=subprocess.CalledProcessError(1, "tasklist")), self.assertRaises(subprocess.CalledProcessError):
            REPAIR.require_closed()

    def test_mpq_unsafe_members_rejected(self):
        mpq = object.__new__(REPAIR.Mpq)
        for name in ("..\\evil", "x/evil", "AUX.txt", "a:evil"):
            with self.subTest(name=name), patch.object(mpq, "call", return_value="(listfile)\n(attributes)\n" + name + "\n"):
                with self.assertRaises(ValueError):
                    mpq.names(Path("unused"), 3)

    def test_mpq_case_collision_rejected(self):
        mpq = object.__new__(REPAIR.Mpq)
        with patch.object(mpq, "call", return_value="(listfile)\n(attributes)\na\nA\n"), self.assertRaises(ValueError):
            mpq.names(Path("unused"), 4)

    def test_long_extraction_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "shorter"):
            REPAIR.extract_paths(Path(tempfile.gettempdir()) / ("x" * 200), ["a" * 90])


class Installation(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.client, self.artifacts, self.sources = [self.root / name for name in ("client", "artifacts", "sources")]
        for path in (self.client, self.artifacts, self.sources):
            path.mkdir()
        self.manifest = {"schema": 1, "id": "fixture", "archive": "Data/patch-B.MPQ", "members": {},
                         "optional_loose": {"Interface/AddOns/WeakAuras/Prototypes.lua": {}},
                         "protected_identity": {"Ascension.exe": hash_bytes(b"identity")},
                         "retire_addon": "Interface/AddOns/COAWeakAurasRange"}
        (self.sources / "g1-client-manifest.json").write_text(json.dumps(self.manifest))
        self.patches = [patch.object(REPAIR, "PATCHES", self.sources),
                        patch.object(REPAIR, "MANIFEST", self.sources / "g1-client-manifest.json"),
                        patch.object(REPAIR, "require_closed")]
        for mocked in self.patches:
            mocked.start()
            self.addCleanup(mocked.stop)
        self.file("Ascension.exe", b"identity")
        self.file("WTF/Account/Player/SavedVariables/WeakAuras.lua", b"valuable auras")
        self.file("Interface/AddOns/Unrelated/file.lua", b"unrelated addon")
        self.file(self.manifest["retire_addon"] + "/legacy.lua", b"old helper")
        self.entries = []
        for index, name in enumerate((self.manifest["archive"], *self.manifest["optional_loose"])):
            old, new = ("old" + str(index)).encode(), ("new" + str(index)).encode()
            self.file(name, old)
            (self.artifacts / f"{index}.before").write_bytes(old)
            (self.artifacts / f"{index}.prepared").write_bytes(new)
            self.entries.append({"target": name, "before": hash_bytes(old), "after": hash_bytes(new),
                                 "backup": f"{index}.before", "prepared": f"{index}.prepared"})
        self.proof = {"schema": 1, "status": "prepared", "client": str(self.client), "artifacts": str(self.artifacts),
                      "manifest_id": "fixture", "source": REPAIR.source_inventory(self.manifest),
                      "script_sha256": REPAIR.sha(SCRIPT), "entries": self.entries,
                      "helper": REPAIR.tree(self.client / self.manifest["retire_addon"])}
        self.write_proof()
        self.args = argparse.Namespace(client=self.client, artifacts=self.artifacts)

    def file(self, name, content):
        path = self.client / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def write_proof(self):
        (self.artifacts / "prepared.json").write_text(json.dumps(self.proof))

    def assert_originals(self):
        for entry in self.entries:
            self.assertEqual(REPAIR.sha(self.client / entry["target"]), entry["before"])

    def test_install_and_rollback_preserve_unrelated_files(self):
        before = REPAIR.tree(self.client)
        REPAIR.install(self.args)
        self.assertFalse((self.client / self.manifest["retire_addon"]).exists())
        for entry in self.entries:
            self.assertEqual(REPAIR.sha(self.client / entry["target"]), entry["after"])
        self.assertEqual((self.client / "WTF/Account/Player/SavedVariables/WeakAuras.lua").read_bytes(), b"valuable auras")
        REPAIR.rollback(self.args)
        self.assertEqual(REPAIR.tree(self.client), before)

    def test_install_replay_rejected(self):
        REPAIR.install(self.args)
        with self.assertRaises(ValueError):
            REPAIR.install(self.args)

    def test_stale_source_refused(self):
        (self.sources / "g1-client-manifest.json").write_text(json.dumps(self.manifest) + "\n")
        with self.assertRaises(ValueError):
            REPAIR.install(self.args)
        self.assert_originals()

    def test_stale_client_refused_before_any_write(self):
        self.file(self.entries[-1]["target"], b"user edit")
        with self.assertRaises(ValueError):
            REPAIR.install(self.args)
        self.assertEqual(REPAIR.sha(self.client / self.entries[0]["target"]), self.entries[0]["before"])

    def test_changed_prepared_file_refused(self):
        (self.artifacts / self.entries[0]["prepared"]).write_bytes(b"changed")
        with self.assertRaises(ValueError):
            REPAIR.install(self.args)
        self.assert_originals()

    def test_rollback_refuses_later_user_edit(self):
        REPAIR.install(self.args)
        self.file(self.entries[-1]["target"], b"later user edit")
        with self.assertRaises(ValueError):
            REPAIR.rollback(self.args)
        self.assertEqual(REPAIR.sha(self.client / self.entries[0]["target"]), self.entries[0]["after"])

    def test_partial_failure_is_recoverable(self):
        actual = REPAIR.replace_file
        calls = []
        def fail_second(*args):
            calls.append(args)
            if len(calls) == 2:
                raise OSError("simulated failure")
            actual(*args)
        with patch.object(REPAIR, "replace_file", side_effect=fail_second), self.assertRaises(OSError):
            REPAIR.install(self.args)
        self.assertTrue((self.artifacts / "failed.json").exists())
        REPAIR.rollback(self.args)
        self.assert_originals()

    def test_redirected_target_rejected(self):
        self.proof["entries"][0]["target"] = "WTF/Account/Player/SavedVariables/WeakAuras.lua"
        self.write_proof()
        with self.assertRaises(ValueError):
            REPAIR.install(self.args)
        self.assertEqual((self.client / "WTF/Account/Player/SavedVariables/WeakAuras.lua").read_bytes(), b"valuable auras")

    def test_different_client_rejected(self):
        with self.assertRaises(ValueError):
            REPAIR.install(argparse.Namespace(client=self.root, artifacts=self.artifacts))
        self.assert_originals()


if __name__ == "__main__":
    unittest.main()
