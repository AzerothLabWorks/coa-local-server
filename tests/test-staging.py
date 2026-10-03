#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("staging", ROOT / "scripts/create-coa-staging.py")
staging = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(staging)


class StagingGuards(unittest.TestCase):
    def test_paths_and_project_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            live = base / "live"
            live.mkdir()
            staging.validate_destination(live, base / "new-stage", "coa-staging-g1")
            for target in (live, live / "child", base):
                with self.assertRaisesRegex(ValueError, "overlap"):
                    staging.validate_destination(live, target, "coa-staging-g1")
            other = base / "existing-stage"
            other.mkdir()
            with self.assertRaisesRegex(ValueError, "already exists"):
                staging.validate_destination(live, other, "coa-staging-g1")

    def test_rejects_live_project_and_existing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            live = base / "live"
            target = base / "new-stage"
            with self.assertRaisesRegex(ValueError, "distinct"):
                staging.validate_destination(live, target, "coa-local")
            target.mkdir()
            with self.assertRaisesRegex(ValueError, "already exists"):
                staging.validate_destination(live, target, "coa-staging-g1")

    def test_env_values_and_permissions(self):
        self.assertEqual(staging.env_text({"VALUE": "x$y"}, raw=True), "VALUE=x$y\n")
        self.assertEqual(staging.env_text({"VALUE": "x$y"}), 'VALUE="x$$y"\n')
        for values in ({"BAD-KEY": "value"}, {"VALUE": "one\ntwo"}):
            with self.assertRaises(ValueError):
                staging.env_text(values)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret"
            staging.write_private(path, "private")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_signature_rejects_missing_schema_and_unknown_checksum(self):
        with patch.object(staging, "sql", return_value="acore_auth\taccount\tInnoDB\tutf8mb4_general_ci\n"):
            with self.assertRaisesRegex(RuntimeError, "four expected schemas"):
                staging.database_signature("fixture")
        tables = "".join(f"{name}\tfixture\tInnoDB\tutf8mb4_general_ci\n" for name in staging.SCHEMAS)
        with patch.object(staging, "sql", side_effect=[tables, "columns", "acore_auth.fixture\tNULL\n"]):
            with self.assertRaisesRegex(RuntimeError, "checksum is unavailable"):
                staging.database_signature("fixture")

    def test_signature_is_content_aware(self):
        tables = "".join(f"{name}\tfixture\tInnoDB\tutf8mb4_general_ci\n" for name in staging.SCHEMAS)
        checksums = "".join(f"{name}.fixture\t123\n" for name in staging.SCHEMAS)
        counts = "".join(f"{name}.fixture\t4\n" for name in staging.SCHEMAS)
        with patch.object(staging, "sql", side_effect=[tables, "columns", checksums, counts, "indexes", ""]) as query:
            result = staging.database_signature("fixture")
            self.assertEqual(result["counts"], counts)
            self.assertIn("EXTENDED", query.call_args_list[2].args[1])
            self.assertEqual(query.call_args_list[3].args[1].count("COUNT(*)"), 4)

    def test_rejects_truncated_signature(self):
        tables = "".join(f"{name}\tfixture\tInnoDB\tutf8mb4_general_ci\n" for name in staging.SCHEMAS)
        with patch.object(staging, "sql", side_effect=[tables, "columns", "", ""]):
            with self.assertRaisesRegex(RuntimeError, "Incomplete checksums"):
                staging.database_signature("fixture")

    def test_live_restart_failure_is_explicit(self):
        services = {role: {"Id": role, "Name": f"/live-{role}"} for role in ("authserver", "worldserver")}
        with patch.object(staging, "run"), patch.object(staging.time, "sleep"), \
                patch.object(staging, "inspect", return_value={"State": {"Running": False}}):
            with self.assertRaisesRegex(RuntimeError, "docker start live-authserver live-worldserver"):
                staging.resume_live(services, "/private/checkpoint")

    def test_capture_failure_always_restores_live_services(self):
        services = {role: {"Id": role} for role in ("database", "authserver", "worldserver")}
        state = {"State": {"Running": False, "OOMKilled": False, "ExitCode": 0}}
        with patch.object(staging, "run"), patch.object(staging, "inspect", return_value=state), \
                patch.object(staging, "database_signature", return_value={}), \
                patch.object(staging, "dump_database", side_effect=RuntimeError("fixture capture failed")), \
                patch.object(staging, "resume_live") as resume:
            with self.assertRaisesRegex(RuntimeError, "fixture capture failed"):
                staging.capture_database_checkpoint(services, Path("/fixture/checkpoint"), {})
            resume.assert_called_once_with(services, Path("/fixture/checkpoint"))

    def test_forced_shutdown_is_not_a_qualified_checkpoint(self):
        services = {role: {"Id": role} for role in ("database", "authserver", "worldserver")}
        state = {"State": {"Running": False, "OOMKilled": False, "ExitCode": 137}}
        with patch.object(staging, "run"), patch.object(staging, "inspect", return_value=state), \
                patch.object(staging, "database_signature") as signature, \
                patch.object(staging, "resume_live") as resume:
            with self.assertRaisesRegex(RuntimeError, "did not stop cleanly"):
                staging.capture_database_checkpoint(services, Path("/fixture/checkpoint"), {})
            signature.assert_not_called()
            resume.assert_called_once()

    def test_preserved_manifest_is_written_and_detects_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory)
            for name in ("databases.sql", "active-source.tar.gz", "installer-source.tar.gz", "runtime-images.tar"):
                (checkpoint / name).write_bytes(b"fixture")
            (checkpoint / "data").mkdir()
            (checkpoint / "data/fixture.dbc").write_bytes(b"fixture")
            metadata = {"database_dump_sha256": staging.digest(checkpoint / "databases.sql")}
            staging.seal_checkpoint(checkpoint, metadata)
            saved = json.loads((checkpoint / "checkpoint.json").read_text())
            self.assertEqual(len(saved["archive_sha256"]), 3)
            (checkpoint / "data/fixture.dbc").write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "server data changed"):
                staging.seal_checkpoint(checkpoint, metadata)

    def test_resume_identity_and_phase_are_checked_before_docker(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            live, target = base / "live", base / "staging"
            checkpoint = live / "state/backups/g1-baseline-fixture"
            checkpoint.mkdir(parents=True)
            args = SimpleNamespace(live_dir=str(live), dir=str(target), project="coa-staging-g1", resume_checkpoint=str(checkpoint))
            metadata = {"live_runtime": str(live), "staging_runtime": str(target), "project": "coa-local", "status": "database-captured"}
            staging.write_json(checkpoint / "checkpoint.json", metadata)
            with patch.object(staging, "seal_checkpoint") as seal, patch.object(staging, "run") as run:
                with self.assertRaisesRegex(ValueError, "identity"):
                    staging.resume_checkpoint(args)
                metadata["project"] = args.project
                metadata["status"] = "baseline-restored"
                staging.write_json(checkpoint / "checkpoint.json", metadata)
                with self.assertRaisesRegex(ValueError, "not awaiting"):
                    staging.resume_checkpoint(args)
                seal.assert_not_called()
                run.assert_not_called()

    def test_baseline_template_has_no_bootstrap_or_live_storage(self):
        template = (ROOT / "compose.staging.yaml").read_text()
        for forbidden in ("world-bootstrap:", "db-import:", "playerbots-bootstrap:", "coa-local-etc", "coa-local_default"):
            self.assertNotIn(forbidden, template)
        self.assertEqual(template.count('"127.0.0.1:${COA_STAGING_'), 3)
        database = template.split("  database:", 1)[1].split("  authserver:", 1)[0]
        self.assertNotIn("ports:", database)
        self.assertEqual(template.count("      - staging-ingress"), 2)
        for setting in ("AC_UPDATES_ENABLE_DATABASES: 0", "AC_PLAYERBOTS_UPDATES_ENABLE_DATABASES: 0",
                        "AC_UPDATES_AUTO_SETUP: 0", "AC_SOAP_ENABLED: 0", "AC_RA_ENABLE: 0"):
            self.assertIn(setting, template)
        self.assertIn("internal: true", template)
        self.assertIn("--protocol=TCP", template)
        self.assertNotIn("mysqladmin ping", template)


if __name__ == "__main__":
    unittest.main()
