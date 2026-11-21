"""Synthetic archive and recovery tests; no client, assets, executable or network required."""
import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wardrobe_repair", ROOT / "scripts/wardrobe-repair.py")
REPAIR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPAIR)
MPQ = __import__("wardrobe_mpq")
MASK = 0xFFFFFFFF


def digest(value):
    return hashlib.sha256(value).hexdigest()


def encrypt_table(data, key):
    # A fixture writer implements the MPQ encryption direction. The production
    # reader implements decryption; it never creates these archives or assets.
    table, seed = [0] * 1280, 0x100001
    for low in range(256):
        for high in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            upper = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            table[high * 256 + low] = upper | (seed & 0xFFFF)
    output, seed = bytearray(), 0xEEEEEEEE
    for (plain,) in struct.iter_unpack("<I", data):
        seed = (seed + table[1024 + (key & 255)]) & MASK
        output.extend(struct.pack("<I", (plain ^ (key + seed)) & MASK))
        key = (((((~key) & MASK) << 21) + 0x11111111) | (key >> 11)) & MASK
        seed = (plain + seed + (seed << 5) + 3) & MASK
    return output


def archive(path, entries, *, version=0):
    """Write tiny valid MPQs with plaintext payloads and encrypted index tables.

    Entries are (name, payload[, locale[, platform[, flags]]]). Payloads are
    artificial text; no real game data is included in the tests.
    """
    header_size = 32 if version == 0 else 44
    capacity = 1
    while capacity < max(2, len(entries) * 2):
        capacity *= 2
    hashes = [b"\xff" * 16 for _ in range(capacity)]
    payload, blocks = bytearray(), bytearray()
    for index, entry in enumerate(entries):
        name, data = entry[:2]
        locale = entry[2] if len(entry) > 2 else 0
        platform = entry[3] if len(entry) > 3 else 0
        flags = entry[4] if len(entry) > 4 else 0x80000000
        slot = MPQ.name_hash(name, 0) & (capacity - 1)
        while hashes[slot] != b"\xff" * 16:
            slot = (slot + 1) & (capacity - 1)
        hashes[slot] = struct.pack("<IIHBBI", MPQ.name_hash(name, 1), MPQ.name_hash(name, 2), locale, platform, 0, index)
        blocks.extend(struct.pack("<4I", header_size + len(payload), len(data), len(data), flags))
        payload.extend(data)
    hash_offset = header_size + len(payload)
    block_offset = hash_offset + capacity * 16
    size = block_offset + len(blocks)
    header = struct.pack("<4s2I2H4I", b"MPQ\x1a", header_size, size, version, 3,
                         hash_offset, block_offset, capacity, len(entries))
    if version == 1:
        header += struct.pack("<Q2H", 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + payload + encrypt_table(b"".join(hashes), MPQ.name_hash("(hash table)", 3))
                     + encrypt_table(blocks, MPQ.name_hash("(block table)", 3)))
    return path


class FixtureMpq:
    def __init__(self, *unused):
        pass

    def read(self, path, name):
        row = REPAIR.neutral_unique(MPQ.numeric_inventory(path), name)
        data = Path(path).read_bytes()
        return data[row["offset"]:row["offset"] + row["size"]]


class NumericArchives(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_known_real_member_hash_and_case_normalization(self):
        name = "ITEM\\OBJECTCOMPONENTS\\collections\\armor_scribe_d_01_ArmLower_Right_be_f.m2"
        self.assertEqual(MPQ.name_hash(name, 1), 0xFC5B9BD5)
        self.assertEqual(MPQ.name_hash(name, 2), 0x1C5D6720)
        self.assertEqual(MPQ.name_hash(name.lower().replace("\\", "/"), 1), 0xFC5B9BD5)

    def test_both_supported_headers_and_payload_bounds(self):
        for version in (0, 1):
            with self.subTest(version=version):
                path = archive(self.root / str(version), [("a", b"fixture")], version=version)
                rows = MPQ.numeric_inventory(path)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["size"], 7)
                self.assertEqual(FixtureMpq().read(path, "A"), b"fixture")

    def test_duplicate_neutral_and_english_locales_are_distinct(self):
        original = archive(self.root / "before", [("a", b"old")])
        duplicated = archive(self.root / "duplicate", [("a", b"old"), ("a", b"new", 0x409)])
        rows = MPQ.member_rows(MPQ.numeric_inventory(duplicated), "a")
        self.assertEqual({row["locale"] for row in rows}, {0, 0x409})
        with self.assertRaisesRegex(ValueError, "identities changed"):
            MPQ.verify_identity(original, duplicated)
        with self.assertRaisesRegex(ValueError, "duplicate or non-neutral"):
            REPAIR.neutral_unique(rows, "a")

    def test_platform_or_name_change_is_not_an_equivalent_rewrite(self):
        original = archive(self.root / "original", [("a", b"old")])
        for entry in (("a", b"new", 0, 1), ("b", b"new"), ("a", b"new", 0x409)):
            with self.subTest(entry=entry):
                changed = archive(self.root / "changed", [entry])
                with self.assertRaises(ValueError):
                    MPQ.verify_identity(original, changed)

    def test_payload_changes_are_not_claimed_as_identity_validation(self):
        original = archive(self.root / "before", [("a", b"old")])
        changed = archive(self.root / "after", [("a", b"new data")])
        self.assertTrue(MPQ.verify_identity(original, changed)["passed"])

    def test_header_bounds_and_unsupported_layouts_fail_closed(self):
        valid = archive(self.root / "valid", [("a", b"fixture")], version=1).read_bytes()
        cases = [valid[:12], b"junk" + valid, valid[:28]]
        for offset, fmt, value in ((12, "H", 2), (4, "I", 45), (16, "I", 0xFFFFFFF0),
                                   (24, "I", 3), (32, "Q", 1), (20, "I", struct.unpack_from("<I", valid, 16)[0])):
            changed = bytearray(valid)
            struct.pack_into("<" + fmt, changed, offset, value)
            cases.append(changed)
        for index, data in enumerate(cases):
            with self.subTest(case=index):
                path = self.root / "bad"
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    MPQ.numeric_inventory(path)

    def test_active_block_must_exist(self):
        path = archive(self.root / "absent", [("a", b"data", 0, 0, 0)])
        with self.assertRaisesRegex(ValueError, "nonexistent"):
            MPQ.numeric_inventory(path)


class ClientFixture(unittest.TestCase):
    LEFT, RIGHT = "Item/Arm-left.m2", "Item/Arm-right.m2"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.client, self.artifacts = self.root / "client", self.root / "artifacts"
        self.client.mkdir()
        self.artifacts.mkdir()
        self.target, self.donor = self.client / "Data/patch-U.MPQ", self.client / "Data/patch-TA.MPQ"
        self.bad = {self.LEFT: b"brokenLEFT", self.RIGHT: b"brokenRGHT"}
        self.good = {self.LEFT: b"fixed-LEFT", self.RIGHT: b"fixed-RGHT"}
        self.skins = {self.LEFT + ".skin": b"skinLEFT", self.RIGHT + ".skin": b"skinRIGHT"}
        self.exe = self.client / "Ascension.exe"
        self.exe.write_bytes(b"synthetic executable identity")
        self.write_target(self.bad)
        self.write_donor()
        self.manifest = {
            "schema": 1, "id": "synthetic-wardrobe", "archive": "Data/patch-U.MPQ",
            "donor_archive": "Data/patch-TA.MPQ", "archive_members": 3,
            "repairable_archive_sha256": [REPAIR.sha(self.target)], "mpqcli_sha256": "unused-test-tool",
            "protected_identity": {"Ascension.exe": REPAIR.sha(self.exe)},
            "members": [{"path": name, "skin": name + ".skin", "locale": 0,
                         "broken_sha256": digest(self.bad[name]), "repaired_sha256": digest(self.good[name]),
                         "skin_sha256": digest(self.skins[name + ".skin"])} for name in (self.LEFT, self.RIGHT)],
        }
        self.args = argparse.Namespace(client=self.client, artifacts=self.artifacts, mpq_tool=self.root / "unused")

    def write_target(self, values, *, unrelated=b"valuable-other-model", extra=()):
        return archive(self.target, [(name, values[name]) for name in (self.LEFT, self.RIGHT)]
                       + [("Unrelated.m2", unrelated)] + list(extra))

    def write_donor(self, values=None):
        values = values or {**self.good, **self.skins}
        return archive(self.donor, list(values.items()))

    def inspect(self):
        return REPAIR.inspect_client(self.client, self.manifest, FixtureMpq())


class ClientInspection(ClientFixture):
    def test_known_broken_and_fixed_states(self):
        self.assertEqual(self.inspect()["status"], "repair-needed")
        self.write_target(self.good)
        self.assertEqual(self.inspect()["status"], "fixed")

    def test_future_unrecognized_model_is_not_overwritten(self):
        self.write_target({**self.good, self.LEFT: b"potential upstream fix"})
        before = self.target.read_bytes()
        with self.assertRaisesRegex(ValueError, "may be newer"):
            self.inspect()
        self.assertEqual(self.target.read_bytes(), before)

    def test_unknown_donor_or_skin_requires_review(self):
        for name in (self.LEFT, self.LEFT + ".skin"):
            with self.subTest(member=name):
                self.write_donor({**self.good, **self.skins, name: b"new version"})
                with self.assertRaisesRegex(ValueError, "Unknown donor|Unknown paired skin"):
                    self.inspect()
                self.write_donor()

    def test_new_archive_override_even_in_locale_folder_requires_review(self):
        archive(self.client / "Data/enUS/patch-new.mpq", [(self.LEFT, self.good[self.LEFT])])
        with self.assertRaisesRegex(ValueError, "model providers"):
            self.inspect()

    def test_new_skin_override_requires_review(self):
        archive(self.client / "Data/patch-Z.MPQ", [(self.LEFT + ".skin", self.skins[self.LEFT + ".skin"])])
        with self.assertRaisesRegex(ValueError, "skin providers"):
            self.inspect()

    def test_duplicate_locale_cannot_masquerade_as_repaired(self):
        self.write_target(self.good, extra=[(self.LEFT, self.bad[self.LEFT], 0x409)])
        with self.assertRaisesRegex(ValueError, "duplicate or non-neutral"):
            self.inspect()

    def test_partial_repair_and_changed_broken_archive_require_review(self):
        for values, other in (({**self.bad, self.LEFT: self.good[self.LEFT]}, b"valuable-other-model"),
                              (self.bad, b"new upstream unrelated model")):
            with self.subTest(other=other, values=values):
                self.write_target(values, unrelated=other)
                with self.assertRaisesRegex(ValueError, "partially repaired"):
                    self.inspect()

    def test_changed_executable_requires_review(self):
        self.exe.write_bytes(b"new executable")
        with self.assertRaisesRegex(ValueError, "Unsupported client executable"):
            self.inspect()

    def test_audit_exit_codes_and_read_only_behavior(self):
        with patch.object(REPAIR, "recipe", return_value=self.manifest), patch.object(REPAIR, "Mpq", FixtureMpq):
            for values, expected in ((self.bad, 2), (self.good, 0), ({**self.good, self.LEFT: b"unknown"}, 3)):
                with self.subTest(expected=expected):
                    self.write_target(values)
                    before = {str(p): p.read_bytes() for p in self.client.rglob("*") if p.is_file()}
                    output = io.StringIO()
                    with redirect_stdout(output):
                        self.assertEqual(REPAIR.audit(self.args), expected)
                    self.assertFalse(json.loads(output.getvalue())["client_modified"])
                    after = {str(p): p.read_bytes() for p in self.client.rglob("*") if p.is_file()}
                    self.assertEqual(after, before)


class Recovery(ClientFixture):
    def setUp(self):
        super().setUp()
        self.backup, self.candidate = self.artifacts / "archive.before.mpq", self.artifacts / "archive.prepared.mpq"
        self.backup.write_bytes(self.target.read_bytes())
        archive(self.candidate, [(name, self.good[name]) for name in (self.LEFT, self.RIGHT)]
                + [("Unrelated.m2", b"valuable-other-model")])
        self.sources = {"fixture-source": "fixed-source-digest"}
        self.proof = {
            "schema": 1, "status": "prepared", "manifest_id": self.manifest["id"],
            "client": str(self.client), "artifacts": str(self.artifacts),
            "before": REPAIR.sha(self.backup), "after": REPAIR.sha(self.candidate),
            "source_identity": self.sources,
            "qualification": REPAIR.verify_candidate(self.backup, self.candidate, self.manifest, FixtureMpq()),
        }
        self.write_proof()
        for mocked in (patch.object(REPAIR, "recipe", return_value=self.manifest),
                       patch.object(REPAIR, "Mpq", FixtureMpq),
                       patch.object(REPAIR, "source_identity", return_value=self.sources),
                       patch.object(REPAIR, "artifact_paths", return_value=(self.client, self.artifacts)),
                       patch.object(REPAIR, "windows_path", side_effect=str),
                       patch.object(REPAIR.C, "require_closed")):
            mocked.start()
            self.addCleanup(mocked.stop)

    def write_proof(self):
        (self.artifacts / "prepared.json").write_text(json.dumps(self.proof))

    def write_attempt(self):
        (self.artifacts / "attempt.json").write_text(json.dumps({"prepared_sha256": REPAIR.sha(self.artifacts / "prepared.json")}))

    def test_full_fixture_install_and_rollback_preserve_unrelated_content(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(REPAIR.install(self.args), 0)
            self.assertEqual(self.target.read_bytes(), self.candidate.read_bytes())
            self.assertEqual(FixtureMpq().read(self.target, "Unrelated.m2"), b"valuable-other-model")
            self.assertEqual(REPAIR.rollback(self.args), 0)
        self.assertEqual(self.target.read_bytes(), self.backup.read_bytes())
        self.assertTrue((self.artifacts / "installed.json").exists())

    def test_candidate_rejects_unrelated_byte_change(self):
        archive(self.candidate, [(name, self.good[name]) for name in (self.LEFT, self.RIGHT)]
                + [("Unrelated.m2", b"VALUABLE-other-model")])
        with self.assertRaisesRegex(ValueError, "Unrelated archive contents"):
            REPAIR.verify_candidate(self.backup, self.candidate, self.manifest, FixtureMpq())

    def test_candidate_rejects_unrelated_flag_change(self):
        archive(self.candidate, [(name, self.good[name]) for name in (self.LEFT, self.RIGHT)]
                + [("Unrelated.m2", b"valuable-other-model", 0, 0, 0x80000001)])
        with self.assertRaisesRegex(ValueError, "Unrelated archive metadata"):
            REPAIR.verify_candidate(self.backup, self.candidate, self.manifest, FixtureMpq())

    def test_receipt_from_changed_recipe_is_rejected(self):
        self.proof["source_identity"] = {"fixture-source": "different"}
        self.write_proof()
        with self.assertRaisesRegex(ValueError, "receipt does not match"):
            REPAIR.load_proof(self.args)

    def test_modified_recovery_files_are_rejected(self):
        for path in (self.backup, self.candidate):
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                with self.assertRaisesRegex(ValueError, "Recovery package changed"):
                    REPAIR.load_proof(self.args)
                path.write_bytes(original)

    def test_install_refuses_archive_changed_after_preparation(self):
        self.target.write_bytes(b"new updater data")
        before = self.target.read_bytes()
        with self.assertRaises(ValueError):
            REPAIR.install(self.args)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertFalse((self.artifacts / "attempt.json").exists())

    def test_rollback_refuses_later_updater_writes(self):
        self.write_attempt()
        self.target.write_bytes(b"later update must survive")
        with self.assertRaisesRegex(ValueError, "Archive changed since installation"):
            REPAIR.rollback(self.args)
        self.assertEqual(self.target.read_bytes(), b"later update must survive")

    def test_rollback_requires_matching_install_attempt(self):
        (self.artifacts / "attempt.json").write_text(json.dumps({"prepared_sha256": "different"}))
        with self.assertRaisesRegex(ValueError, "Install attempt does not match"):
            REPAIR.rollback(self.args)

    def test_closed_client_check_happens_before_receipt_or_mutation(self):
        with patch.object(REPAIR.C, "require_closed", side_effect=ValueError("Fully close the game")), \
                patch.object(REPAIR, "artifact_paths") as paths:
            with self.assertRaisesRegex(ValueError, "Fully close"):
                REPAIR.load_proof(self.args)
            paths.assert_not_called()


class RecipeSnapshot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.artifacts = Path(self.temp.name)
        self.sources = REPAIR.source_identity()

    def test_snapshot_contains_exact_complete_recovery_recipe(self):
        REPAIR.snapshot_recipe(self.artifacts, self.sources)
        saved = {path.relative_to(self.artifacts / "recipe").as_posix(): REPAIR.sha(path)
                 for path in (self.artifacts / "recipe").rglob("*") if path.is_file()}
        self.assertEqual(saved, self.sources)
        self.assertEqual(len(saved), 4)

    def test_snapshot_refuses_existing_destination_without_overwrite(self):
        destination = self.artifacts / "recipe"
        destination.mkdir()
        sentinel = destination / "keep.txt"
        sentinel.write_bytes(b"previous recovery tools")
        with self.assertRaisesRegex(ValueError, "snapshot already exists"):
            REPAIR.snapshot_recipe(self.artifacts, self.sources)
        self.assertEqual(sentinel.read_bytes(), b"previous recovery tools")
        self.assertEqual(list(destination.iterdir()), [sentinel])

    def test_snapshot_refuses_source_identity_that_changed_before_copy(self):
        stale = dict(self.sources)
        stale["scripts/wardrobe-repair.py"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "changed while saving recovery tools"):
            REPAIR.snapshot_recipe(self.artifacts, stale)

    def test_saved_script_imports_and_hashes_its_own_recipe_in_fresh_process(self):
        REPAIR.snapshot_recipe(self.artifacts, self.sources)
        saved_root = self.artifacts / "recipe"
        code = (
            "import importlib.util,json,sys; "
            "spec=importlib.util.spec_from_file_location('saved_repair',sys.argv[1]); "
            "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
            "print(json.dumps({'root':str(module.ROOT),'sources':module.source_identity(),"
            "'manifest_id':module.recipe()['id'],'helper':sys.modules['wardrobe_mpq'].__file__}))"
        )
        result = subprocess.run([sys.executable, "-B", "-I", "-c", code,
                                 str(saved_root / "scripts/wardrobe-repair.py")],
                                cwd=self.artifacts, check=True, capture_output=True, text=True)
        report = json.loads(result.stdout)
        self.assertEqual(Path(report["root"]), saved_root)
        self.assertEqual(report["sources"], self.sources)
        self.assertEqual(report["manifest_id"], REPAIR.recipe()["id"])
        self.assertEqual(Path(report["helper"]), saved_root / "scripts/wardrobe_mpq.py")


class ProcessGuard(unittest.TestCase):
    def test_repository_manifest_has_exact_hashes_and_narrow_scope(self):
        manifest = REPAIR.recipe()
        self.assertEqual(manifest["archive"], "Data/patch-U.MPQ")
        self.assertEqual(manifest["donor_archive"], "Data/patch-TA.MPQ")
        self.assertEqual(manifest["archive_members"], 38204)
        self.assertEqual(len(manifest["members"]), 2)
        hashes = [manifest["mpqcli_sha256"], manifest["reference_repaired_archive_sha256"],
                  *manifest["repairable_archive_sha256"], *manifest["protected_identity"].values()]
        for member in manifest["members"]:
            self.assertEqual(member["locale"], 0)
            self.assertRegex(member["path"], r"(?i)armor_scribe_d_01_armlower_(left|right)_be_f\.m2$")
            self.assertEqual(member["skin"], member["path"][:-3] + "00.skin")
            self.assertNotEqual(member["broken_sha256"], member["repaired_sha256"])
            hashes.extend(member[key] for key in ("broken_sha256", "repaired_sha256", "skin_sha256"))
        for value in hashes:
            self.assertRegex(value, r"^[0-9a-f]{64}$")

    def test_running_windows_client_and_launcher_are_rejected(self):
        for name in ("Ascension.exe", "MMgr64.exe", "Wow.exe", "WoW-64.exe"):
            result = subprocess.CompletedProcess([], 0, stdout=f'"{name}","123","Console","1","20 K"\n')
            with self.subTest(process=name), patch.object(REPAIR.C.os, "name", "nt"), \
                    patch.object(REPAIR.C.subprocess, "run", return_value=result), self.assertRaisesRegex(ValueError, "Fully close"):
                REPAIR.C.require_closed()

    def test_failed_process_inventory_is_not_treated_as_closed(self):
        with patch.object(REPAIR.C.os, "name", "nt"), \
                patch.object(REPAIR.C.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "tasklist")), \
                self.assertRaises(subprocess.CalledProcessError):
            REPAIR.C.require_closed()


if __name__ == "__main__":
    unittest.main()
