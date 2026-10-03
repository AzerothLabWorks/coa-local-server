#!/usr/bin/env python3
from collections import Counter
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("restore_proof", ROOT / "scripts/staging-restore-proof.py")
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)
TABLE = "acore_characters.characters"


def fixture_signature():
    names = {"acore_auth": "fixture", "acore_characters": "characters", "acore_world": "fixture", "acore_playerbots": "fixture"}
    signature = {key: "" for key in proof.SIGNATURE_KEYS}
    for schema, table in sorted(names.items()):
        name = f"{schema}.{table}"
        signature["tables"] += f"{schema}\t{table}\tInnoDB\tutf8mb4_general_ci\n"
        signature["columns"] += f"{schema}\t{table}\tid\t1\tint unsigned\tNO\t<NULL>\t\t<NULL>\n"
        signature["columns"] += f"{schema}\t{table}\tposition_x\t2\tfloat\tNO\t0\t\t<NULL>\n"
        signature["indexes"] += f"{schema}\t{table}\tPRIMARY\t0\t1\tid\t0\tBTREE\tYES\n"
        signature["checksums"] += f"{name}\t100\n"
        signature["counts"] += f"{name}\t2\n"
    return signature


def dump(rows, table="characters", schema="acore_characters", footer=True):
    result = b"-- MySQL dump 10.13 Distrib 8.4.11\n"
    result += f"USE `{schema}`;\n-- Dumping data for table `{table}`\n".encode()
    if rows:
        result += f"INSERT INTO `{table}` VALUES ".encode() + b",".join(rows) + b";\n"
    if footer:
        result += b"-- Dump completed on 2026-10-01 00:00:00\n"
    return result


class CanonicalRestoreProof(unittest.TestCase):
    def test_quoted_delimiters_escapes_and_embedded_newline(self):
        rows = [b"(1,'comma, (paren); and \\'quoted\\' plus \\n escape')", b"(2,'actual\nnewline,here')"]
        parsed = proof.read_dump_rows(io.BytesIO(dump(rows)), {TABLE: 2})[TABLE]
        self.assertEqual(parsed, Counter(rows))
        doubled_quote = b"(1,'it''s, safe')"
        self.assertEqual(proof.split_insert_rows(b"INSERT INTO `characters` VALUES " + doubled_quote + b";", 2), [doubled_quote])

    def test_duplicate_tuples_are_preserved_and_digest_is_order_independent(self):
        first, second = b"(1,1.25)", b"(2,2.5)"
        rows = proof.read_dump_rows(io.BytesIO(dump([first, second, first])), {TABLE: 2})[TABLE]
        self.assertEqual(rows[first], 2)
        self.assertEqual(proof.row_digest(rows), proof.row_digest(Counter([second, first, first])))
        self.assertNotEqual(proof.row_digest(rows), proof.row_digest(Counter([first, second])))

    def test_truncated_or_unsupported_parser_output_fails(self):
        cases = [dump([b"(1,1.25)"], footer=False),
                 b"-- MySQL dump 10.13\nUSE `acore_characters`;\nINSERT INTO `characters` VALUES (1,'unterminated\n",
                 dump([b"(1,1.25)"]) + b"SELECT 1;\n",
                 dump([b"(1,1.25)"]).replace(b"VALUES (1,1.25)", b"VALUES (1,)"),
                 dump([b"(1,1.25)"]).replace(b"VALUES (1,1.25)", b"VALUES (1,1.25),"),
                 dump([b"(1,1.25)"]).replace(b"INSERT INTO `characters` VALUES", b"INSERT INTO `characters` (`id`) VALUES")]
        for data in cases:
            with self.subTest(data_length=len(data)), self.assertRaises(proof.RestoreProofError):
                proof.read_dump_rows(io.BytesIO(data), {TABLE: 2})
        with self.assertRaisesRegex(proof.RestoreProofError, "column count"):
            proof.read_dump_rows(io.BytesIO(dump([b"(1,1.25,3)"])), {TABLE: 2})
        with self.assertRaisesRegex(proof.RestoreProofError, "missing a required table"):
            proof.read_dump_rows(io.BytesIO(dump([], table="different")), {TABLE: 2})

    def test_metadata_only_changes_are_never_excused(self):
        expected = fixture_signature()
        for key in proof.SIGNATURE_KEYS - {"checksums"}:
            changed = copy.deepcopy(expected)
            changed[key] += "changed\n"
            with self.subTest(key=key), self.assertRaisesRegex(proof.RestoreProofError, "metadata differs"):
                proof.validate_signatures(expected, changed)

    def test_non_allowlisted_mismatch_and_non_float_table_fail(self):
        expected = fixture_signature()
        changed = copy.deepcopy(expected)
        changed["checksums"] = changed["checksums"].replace("acore_auth.fixture\t100", "acore_auth.fixture\t200")
        with self.assertRaisesRegex(proof.RestoreProofError, "allowlist"):
            proof.validate_signatures(expected, changed)
        expected["columns"] = expected["columns"].replace("\tfloat\t", "\tdouble\t")
        changed = copy.deepcopy(expected)
        changed["checksums"] = changed["checksums"].replace(TABLE + "\t100", TABLE + "\t200")
        with self.assertRaisesRegex(proof.RestoreProofError, "no FLOAT column"):
            proof.validate_signatures(expected, changed)

    def test_incomplete_or_duplicate_checksum_metadata_fails(self):
        expected = fixture_signature()
        for change in ("", expected["checksums"] + TABLE + "\t100\n", expected["checksums"].replace("100", "NULL", 1)):
            restored = copy.deepcopy(expected)
            restored["checksums"] = change
            with self.subTest(length=len(change)), self.assertRaises(proof.RestoreProofError):
                proof.validate_signatures(expected, restored)

    def test_exact_rows_succeed_but_changes_missing_rows_or_duplicate_loss_fail(self):
        expected = fixture_signature()
        restored = copy.deepcopy(expected)
        restored["checksums"] = restored["checksums"].replace(TABLE + "\t100", TABLE + "\t200")
        tables, counts, differences = proof.validate_signatures(expected, restored)
        rows = [b"(1,1.25)", b"(1,1.25)"]
        result = proof.prove_rows(tables, counts, differences, io.BytesIO(dump(rows)), lambda *_: Counter(rows))
        self.assertEqual(result[TABLE]["original_row_count"], 2)
        self.assertEqual(result[TABLE]["raw_checksums"], {"original": 100, "restored": 200})
        for changed in ([b"(1,1.25)", b"(1,1.26)"], [b"(1,1.25)"], [b"(1,1.25)", b"(2,1.25)"]):
            with self.subTest(row_count=len(changed)), self.assertRaises(proof.RestoreProofError):
                proof.prove_rows(tables, counts, differences, io.BytesIO(dump(rows)), lambda *_: Counter(changed))

    def test_private_evidence_contains_hashes_not_rows_and_catches_dump_tampering(self):
        expected = fixture_signature()
        restored = copy.deepcopy(expected)
        restored["checksums"] = restored["checksums"].replace(TABLE + "\t100", TABLE + "\t200")
        rows = [b"(1,1.25)", b"(2,2.5)"]
        staging = Mock()
        staging.database_signature.return_value = restored
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory)
            data = dump(rows)
            (checkpoint / "databases.sql").write_bytes(data)
            (checkpoint / "checkpoint.json").write_text(json.dumps({
                "database_dump_sha256": hashlib.sha256(data).hexdigest(), "database_signature": expected}))
            with patch.object(proof, "_staging_module", return_value=staging), \
                    patch.object(proof, "_guard_staging"), patch.object(proof, "_redump_rows", return_value=Counter(rows)):
                result = proof.verify_restore("stage-db", checkpoint, expected, restored)
                self.assertEqual(result["status"], "verified")
                self.assertFalse(result["bit_identical_float_storage"])
                evidence = checkpoint / "restore-canonical-proof.json"
                self.assertEqual(evidence.stat().st_mode & 0o777, 0o600)
                self.assertNotIn("(1,1.25)", evidence.read_text())
                (checkpoint / "databases.sql").write_bytes(data + b"\n")
                with self.assertRaisesRegex(proof.RestoreProofError, "SHA-256 changed"):
                    proof.verify_restore("stage-db", checkpoint, expected, restored)
                self.assertEqual(json.loads(evidence.read_text())["status"], "failed")

    def test_signature_change_during_proof_is_rejected(self):
        expected = fixture_signature()
        restored = copy.deepcopy(expected)
        restored["checksums"] = restored["checksums"].replace(TABLE + "\t100", TABLE + "\t200")
        rows = [b"(1,1.25)", b"(2,2.5)"]
        staging = Mock()
        staging.database_signature.return_value = expected
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory)
            data = dump(rows)
            (checkpoint / "databases.sql").write_bytes(data)
            (checkpoint / "checkpoint.json").write_text(json.dumps({
                "database_dump_sha256": hashlib.sha256(data).hexdigest(), "database_signature": expected}))
            with patch.object(proof, "_staging_module", return_value=staging), \
                    patch.object(proof, "_guard_staging"), patch.object(proof, "_redump_rows", return_value=Counter(rows)):
                with self.assertRaisesRegex(proof.RestoreProofError, "changed during"):
                    proof.verify_restore("stage-db", checkpoint, expected, restored)

    def test_staging_guard_rejects_live_or_running_gameplay_services(self):
        staging = Mock()
        staging.inspect.return_value = {"State": {"Running": True}, "Config": {"Labels": {
            "com.docker.compose.project": "coa-local", "com.docker.compose.service": "database"}}}
        with self.assertRaisesRegex(proof.RestoreProofError, "isolated staging"):
            proof._guard_staging("fixture", staging)
        staging.inspect.return_value["Config"]["Labels"]["com.docker.compose.project"] = "coa-staging-g1"
        staging.output.return_value = "database\nworldserver\n"
        with self.assertRaisesRegex(proof.RestoreProofError, "remain stopped"):
            proof._guard_staging("fixture", staging)
        staging.output.return_value = "database\n"
        proof._guard_staging("fixture", staging)


if __name__ == "__main__":
    unittest.main()
