import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("g1_installer", REPO / "scripts/g1.py")
g1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g1)
container_spec = importlib.util.spec_from_file_location("g1_container", REPO / "docker/g1-container.py")
container = importlib.util.module_from_spec(container_spec)
container_spec.loader.exec_module(container)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.artifact = self.root / "core.patch"
        self.artifact.write_text("patch contents\n", encoding="utf-8")
        self.overlay = self.root / "module"
        self.overlay.mkdir()
        (self.overlay / "module.cpp").write_text("source\n", encoding="utf-8")
        self.manifest = {
            "schema_version": 1, "release_id": "g1-test",
            "core": {"repository": "https://github.com/example/core.git", "revision": "a" * 40},
            "playerbots": {"repository": "https://github.com/example/bots.git", "revision": "b" * 40},
            "patches": [{"target": "core", "path": "core.patch", "sha256": g1.digest(self.artifact)}],
            "overlays": [{"source": "module", "target": "modules/mod-local-profession-tools",
                           "files": g1.inventory(self.overlay)}],
            "modules": ["mod-destiny-weaver", "mod-playerbots", "mod-local-profession-tools"],
            "images": {"mysql": "mysql@sha256:" + "c" * 64},
            "data": {"dbc_files": {"Spell.dbc": hashlib.sha256(b"dbc").hexdigest()},
                     "terrain_required": ["maps", "vmaps", "mmaps"]}, "settings": {}}
        self.manifest_path = self.root / "manifest.json"

    def release(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        return g1.release(self.manifest_path, self.root)

    def test_valid_release_artifacts(self):
        self.assertEqual(self.release(), self.manifest)

    def test_changed_patch_refused(self):
        self.artifact.write_text("different", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            self.release()

    def test_untracked_overlay_file_refused(self):
        (self.overlay / "unexpected.cpp").write_text("extra", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "overlay differs"):
            self.release()

    def test_mutable_source_ref_refused(self):
        self.manifest["core"]["revision"] = "main"
        with self.assertRaisesRegex(RuntimeError, "exact public commit"):
            self.release()

    def test_changed_module_selection_refused(self):
        self.manifest["modules"].append("mod-other")
        with self.assertRaisesRegex(RuntimeError, "module set"):
            self.release()

    def test_path_traversal_refused(self):
        for name in ("../outside", "/absolute", ".git/config", "module/../../file", "module\\file"):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                g1.child(self.root, name)

    def test_symlink_artifact_refused(self):
        linked = self.root / "linked"
        try:
            linked.symlink_to(self.artifact)
        except OSError:
            self.skipTest("Symlink creation is not available")
        with self.assertRaisesRegex(RuntimeError, "Symbolic links"):
            g1.ordinary(linked)

    def test_project_names_isolate_directories(self):
        first, second = g1.project_name(self.root / "one"), g1.project_name(self.root / "two")
        self.assertNotEqual(first, second)
        self.assertNotEqual(g1.resource_names(first), g1.resource_names(second))

    def test_unsafe_project_name_refused(self):
        for name in ("coa-local", "../live", "coa-g1-Upper", "coa-g1-one;two", "coa-g1-a b"):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                g1.project_name(self.root, name)

    def test_existing_resource_refused(self):
        with patch.object(g1, "docker_inspect", return_value={"Labels": {}}), self.assertRaisesRegex(RuntimeError, "Existing Docker"):
            g1.absent_resources("coa-g1-test")

    def test_missing_docker_objects_are_case_insensitive(self):
        for error in ("Error: No such container: test", "Error response from daemon: get test: no such volume",
                      "network test not found"):
            with self.subTest(error=error), patch.object(g1.subprocess, "run", return_value=
                    subprocess.CompletedProcess([], 1, "[]", error)):
                self.assertIsNone(g1.docker_inspect("volume", "test"))

    def test_docker_inspect_does_not_hide_daemon_failure(self):
        with patch.object(g1.subprocess, "run", return_value=
                subprocess.CompletedProcess([], 1, "", "Cannot connect to the Docker daemon")), \
                self.assertRaisesRegex(RuntimeError, "inspection failed"):
            g1.docker_inspect("volume", "test")

    def test_port_collision_refused(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            with self.assertRaisesRegex(RuntimeError, "already in use"):
                g1.ports_available([listener.getsockname()[1]])

    def test_duplicate_ports_refused(self):
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            g1.ports_available([3724, 3724])

    def test_private_network_subnet_accepts_available_rfc1918_blocks(self):
        for subnet in ("10.203.29.0/24", "172.20.4.0/24", "192.168.100.0/24"):
            with self.subTest(subnet=subnet):
                self.assertEqual(g1.validate_network_subnet(subnet, [("IPv6 network", "fd00::/64")]), subnet)

    def test_network_subnet_rejects_public_ipv6_non24_or_unaligned(self):
        for subnet in ("8.8.8.0/24", "100.64.1.0/24", "127.0.0.0/24", "169.254.1.0/24", "fd00::/24",
                       "10.203.29.1/24", "10.203.0.0/16", "10.203.29.0/25", "not-a-subnet"):
            with self.subTest(subnet=subnet), self.assertRaisesRegex(RuntimeError, "private IPv4 /24"):
                g1.validate_network_subnet(subnet, [])

    def test_network_subnet_rejects_overlap_with_network_route_and_host(self):
        for occupied in ("10.0.0.0/8", "10.203.29.0/24", "10.203.29.128/25", "10.203.29.3/32"):
            with self.subTest(occupied=occupied), self.assertRaisesRegex(RuntimeError, "overlaps"):
                g1.validate_network_subnet("10.203.29.0/24", [("existing network", occupied)])

    def test_subnet_discovery_reads_docker_and_ignores_only_default_host_route(self):
        outputs = [SimpleNamespace(stdout="abc\n"), SimpleNamespace(stdout=json.dumps([
            {"dst": "default", "gateway": "10.203.29.1"}, {"dst": "0.0.0.0/0"}, {"dst": "172.20.0.0/16"}]))]
        with patch.object(g1.shutil, "which", return_value="/usr/sbin/ip"), patch.object(g1, "run", side_effect=outputs), \
                patch.object(g1, "docker_inspect", return_value={"Name": "retained", "IPAM": {"Config": [{"Subnet": "192.168.0.0/20"}]}}):
            self.assertEqual(g1.available_network_subnet("10.203.29.0/24"), "10.203.29.0/24")

    def test_data_version_mismatch_refused(self):
        for name in ("dbc", "maps", "vmaps", "mmaps"):
            (self.root / name).mkdir()
            (self.root / name / "sample").write_bytes(b"data")
        spell = self.root / "dbc/Spell.dbc"
        spell.write_bytes(b"dbc")
        self.assertEqual(g1.validate_data(self.manifest, self.root, self.root / "dbc", self.root)["dbc"],
                         str(self.root / "dbc"))
        spell.write_bytes(b"wrong version")
        with self.assertRaisesRegex(RuntimeError, "DBC version"):
            g1.validate_data(self.manifest, self.root, self.root / "dbc", self.root)

    def state(self):
        return {"id": "f" * 32, "project": "coa-g1-test", "toolchain_image": "sha256:" + "d" * 64,
                "uid": 1000, "gid": 1000, "ports": {"authserver": 33727, "worldserver": 38088},
                "data": {"base": "/provided", "dbc": "/provided/dbc", "terrain": "/terrain"}}

    def test_compose_has_private_database_and_loopback_game(self):
        composition = g1.composition(self.root, self.state(), self.manifest)
        self.assertNotIn("ports", composition["services"]["database"])
        self.assertIn('"$$MYSQL_ROOT_PASSWORD"', composition["services"]["database"]["healthcheck"]["test"][1])
        for role in ("authserver", "worldserver"):
            service = composition["services"][role]
            self.assertEqual(service["ports"][0]["host_ip"], "127.0.0.1")
            self.assertTrue(service["read_only"])
            targets = {m["target"] for m in service["volumes"]}
            self.assertFalse(targets.intersection({"/g1", "/g1/state", "/g1/control", "/g1/backups"}))
            for name in ("build", "etc", "source"):
                self.assertTrue(next(m for m in service["volumes"] if m["target"] == "/g1/" + name)["read_only"])
            self.assertTrue(next(m for m in service["volumes"] if m["target"] == "/g1/data")["read_only"])
        self.assertEqual(composition["volumes"]["database"]["name"], "coa-g1-test-database")
        self.assertEqual(composition["volumes"]["database"]["labels"][g1.OWNER], "f" * 32)

    def test_unpinned_mysql_refused(self):
        self.manifest["images"]["mysql"] = "mysql:latest"
        with self.assertRaisesRegex(RuntimeError, "digest-pinned"):
            g1.composition(self.root, self.state(), self.manifest)
        with self.assertRaisesRegex(RuntimeError, "digest-pinned"):
            self.release()

    def test_optional_subnet_is_applied_only_to_this_compose_network(self):
        plain = g1.composition(self.root, self.state(), self.manifest)
        self.assertNotIn("ipam", plain["networks"]["default"])
        explicit = g1.composition(self.root, {**self.state(), "network_subnet": "10.203.29.0/24"}, self.manifest)
        self.assertEqual(explicit["networks"]["default"]["ipam"], {"config": [{"subnet": "10.203.29.0/24"}]})

    def test_partial_install_can_be_inspected_without_compose(self):
        state = {**self.state(), "root": str(self.root), "phase": "incomplete"}
        g1.save(self.root / "installation.json", state)
        with patch.object(g1, "docker_inspect", return_value=None):
            self.assertEqual(g1.owned(self.root, ready=False)[1], state)
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                g1.owned(self.root)

    def test_management_refuses_resource_without_owner(self):
        g1.save(self.root / "installation.json", {**self.state(), "root": str(self.root), "phase": "incomplete"})
        with patch.object(g1, "docker_inspect", return_value={"Labels": None}), self.assertRaisesRegex(RuntimeError, "unrelated"):
            g1.owned(self.root, ready=False)

    def test_failed_start_stops_only_created_game_services(self):
        state = {**self.state(), "compose_sha256": "verified"}
        with patch.object(g1, "owned") as ownership, patch.object(g1, "compose") as compose, \
                patch.object(g1, "docker_inspect", side_effect=[{"State": {}}, None]):
            g1.stop_failed_game(self.root, state)
        ownership.assert_called_once_with(self.root, ready=False)
        compose.assert_called_once_with(self.root, "stop", "--timeout", "120", "worldserver")

    def test_incomplete_install_can_stop_owned_database(self):
        state = {**self.state(), "phase": "incomplete", "compose_sha256": "verified"}
        args = SimpleNamespace(command="stop", dir=str(self.root), database=True)
        with patch.object(g1, "prerequisites"), patch.object(g1, "owned", return_value=(self.root, state)) as owned, \
                patch.object(g1, "compose") as compose:
            g1.manage(args)
        owned.assert_called_once_with(self.root, ready=False)
        self.assertEqual(compose.call_args.args, (self.root, "stop", "--timeout", "120", "database"))

    def test_backup_refuses_online_game(self):
        with patch.object(g1, "docker_inspect", return_value={"State": {"Running": True}}), self.assertRaisesRegex(RuntimeError, "Stop the game"):
            g1.backup(self.root, self.state())

    def test_host_proxy_cannot_satisfy_internal_listener_check(self):
        with patch.object(g1.socket, "create_connection") as external, patch.object(g1.subprocess, "run", return_value=
                subprocess.CompletedProcess([], 1, "", "connection refused")):
            self.assertFalse(g1.service_listener_ready(self.state(), "worldserver"))
        external.assert_not_called()

    def test_internal_listener_check_targets_owned_service_and_native_port(self):
        with patch.object(g1.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as process:
            self.assertTrue(g1.service_listener_ready(self.state(), "worldserver"))
        self.assertEqual(process.call_args.args[0][:3], ["docker", "exec", "coa-g1-test-worldserver"])
        self.assertIn("8085", process.call_args.args[0][-1])

    def test_config_replaces_duplicate_values(self):
        config = self.root / "world.conf"
        config.write_text("# example\nUpdates.AutoSetup = 1\nUpdates.AutoSetup = 1\nOther = 5\n", encoding="utf-8")
        container.change_config(config, {"Updates.AutoSetup": "0"})
        text = config.read_text(encoding="utf-8")
        self.assertEqual(text.count("Updates.AutoSetup"), 1)
        self.assertIn("Updates.AutoSetup = 0", text)
        self.assertIn("Other = 5", text)

    def test_config_injection_refused(self):
        config = self.root / "world.conf"
        config.write_text("Original = 1\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Invalid configuration"):
            container.change_config(config, {"Key": "1\nInjected = 1"})
        self.assertEqual(config.read_text(encoding="utf-8"), "Original = 1\n")

    def test_old_mysql_client_is_rejected_before_build(self):
        with patch.object(container.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "unknown option")), \
                self.assertRaisesRegex(RuntimeError, "must support --no-login-paths"):
            container.verify_mysql_client()

    def test_compatible_mysql_client_preserves_no_login_paths_option(self):
        with patch.object(container.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "help", "")) as command:
            container.verify_mysql_client()
        self.assertEqual(command.call_args.args[0], ["/usr/bin/mysql", "--no-defaults", "--no-login-paths", "--help"])
        with patch.object(container, "run", return_value=SimpleNamespace(stdout="0\n")) as command:
            self.assertEqual(container.mysql("SELECT 0;"), "0")
        self.assertEqual(command.call_args.args[0][:3],
                         ["/usr/bin/mysql", "--defaults-extra-file=/g1/state/admin.cnf", "--no-login-paths"])

    def test_bootstrap_requires_empty_database(self):
        with patch.object(container, "STATE", self.root), patch.object(container, "settings", return_value=(
                {"phase": "bootstrap-started", "id": "test", "release_id": "test"}, {})), patch.object(container, "mysql", return_value="1"):
            with self.assertRaisesRegex(RuntimeError, "non-system tables"):
                container.bootstrap()

    def test_bootstrap_never_retries_ambiguous_attempt(self):
        (self.root / "bootstrap-attempt.json").write_text("{}", encoding="utf-8")
        with patch.object(container, "STATE", self.root), patch.object(container, "settings", return_value=(
                {"phase": "bootstrap-started"}, {})), patch.object(container, "mysql") as database:
            with self.assertRaisesRegex(RuntimeError, "never replay"):
                container.bootstrap()
            database.assert_not_called()

    def test_character_dependency_refuses_existing_schema(self):
        with patch.object(container, "mysql", return_value="1") as database, \
                self.assertRaisesRegex(RuntimeError, "new empty schema"):
            container.import_character_schema()
        self.assertEqual(database.call_count, 1)

    def test_character_dependency_follows_complete_base_and_records_identity(self):
        base = self.root / "data/sql/base/db_characters"
        base.mkdir(parents=True)
        for name in ("characters.sql", "updates.sql"):
            (base / name).write_text("SELECT 1;", encoding="utf-8")
        dependency = self.root / "modules/schema.sql"
        dependency.parent.mkdir()
        dependency.write_text("CREATE TABLE ledger(guid INT);", encoding="utf-8")
        imported = []
        def database(query=None, schema=None, file=None):
            if file:
                imported.append(file)
                return ""
            if query.startswith("SELECT COLUMN_TYPE"):
                return "enum('RELEASED','MODULE','ARCHIVED')"
            if query.startswith("SELECT CONCAT"):
                return container.digest(dependency, "sha1") + ":MODULE"
            return "0"
        with patch.object(container, "SOURCE", self.root), patch.object(container, "mysql", side_effect=database), \
                patch.object(container, "CHARACTER_SCHEMA_DEPENDENCIES", {"modules/schema.sql": container.digest(dependency)}):
            result = container.import_character_schema()
        self.assertEqual(imported, [base / "characters.sql", base / "updates.sql", dependency])
        self.assertEqual(result["dependencies"]["schema.sql"]["sha1"], container.digest(dependency, "sha1"))

    def test_canonical_character_dependency_is_pinned(self):
        self.assertEqual(list(container.CHARACTER_SCHEMA_DEPENDENCIES), [
            "modules/mod-worldforged-pickups/data/sql/db-characters/2026_09_16_00_worldforged_loot.sql"])
        self.assertEqual(next(iter(container.CHARACTER_SCHEMA_DEPENDENCIES.values())),
                         "42e4fb03efe4de777c72a8b80b5bc31065c6b454610d4c4635bb61290ef82304")

    def test_runtime_drop_permission_is_limited_to_canonical_truncate_tables(self):
        with patch.object(container, "mysql") as database:
            container.grant_runtime_privileges()
        drop = [call.args[0] for call in database.call_args_list if "GRANT DROP" in call.args[0]]
        self.assertEqual(drop, ["GRANT DROP ON acore_characters.guild_member_withdraw TO 'g1'@'%';",
                                "GRANT DROP ON acore_characters.gm_ticket TO 'g1'@'%';"])

    def test_full_bot_recipe_excludes_custom_vendor_sql(self):
        module = self.root / "modules/mod-playerbots/data/sql/playerbots"
        for part in ("base", "updates", "custom"):
            (module / part).mkdir(parents=True)
        (module / "base/schema.sql").write_text("CREATE TABLE test(id INT);", encoding="utf-8")
        update = module / "updates/one.sql"
        update.write_text("SELECT 1;", encoding="utf-8")
        (module / "custom/destructive.sql").write_text("DROP DATABASE acore_characters;", encoding="utf-8")
        safe = self.root / "data/sql/updates/pending_db_playerbots"
        safe.mkdir(parents=True)
        for name in container.SAFE_BOT_UPDATES:
            (safe / name).write_text("SELECT 1;", encoding="utf-8")
        imported = []
        def database(query=None, schema=None, file=None):
            if file:
                imported.append(file)
                return ""
            if query.startswith("SELECT CONCAT"):
                state = "RELEASED" if "one.sql" in query else "MODULE"
                return container.digest(update, "sha1") + ":" + state
            return "0"
        with patch.object(container, "SOURCE", self.root), patch.object(container, "mysql", side_effect=database):
            ledger = container.import_bot_updates()
        self.assertEqual(len(ledger), 3)
        self.assertEqual(len(imported), 4)
        self.assertFalse(any("custom" in p.parts for p in imported))

    def test_packaged_release_manifest(self):
        manifest = REPO / "releases/g1-20261029/manifest.json"
        if not manifest.is_file():
            self.skipTest("Release artifacts are not present in this checkout")
        self.assertEqual(g1.release(manifest)["release_id"], "g1-20261029")


if __name__ == "__main__":
    unittest.main()
