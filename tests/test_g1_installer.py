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

    def test_worldforged_compilation_requires_separate_sql_allowlist(self):
        original = list(self.manifest["modules"])
        self.manifest["modules"].append("mod-worldforged-pickups")
        with self.assertRaisesRegex(RuntimeError, "placement SQL"):
            self.release()
        self.manifest["migration_modules"] = original
        self.assertEqual(self.release(), self.manifest)
        self.assertEqual(container.migration_modules(self.manifest), original)

    def test_worldforged_placement_migrations_refused_in_host_and_container(self):
        self.manifest["modules"].append("mod-worldforged-pickups")
        self.manifest["migration_modules"] = list(self.manifest["modules"])
        with self.assertRaisesRegex(RuntimeError, "placement SQL"):
            self.release()
        with self.assertRaisesRegex(RuntimeError, "placement SQL"):
            container.migration_modules(self.manifest)

    def test_duplicate_or_uncompiled_migration_modules_refused(self):
        for migrations in (["mod-playerbots"] * 3, ["mod-playerbots", "mod-destiny-weaver", "mod-other"]):
            with self.subTest(migrations=migrations):
                self.manifest["migration_modules"] = migrations
                with self.assertRaisesRegex(RuntimeError, "migration module set"):
                    self.release()
                with self.assertRaisesRegex(RuntimeError, "migration module set"):
                    container.migration_modules(self.manifest)

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

    def test_world_startup_requires_current_start_ready_marker(self):
        entry = {"State": {"StartedAt": "2026-11-18T12:00:00.000000000Z"}}
        for output, ready in (("World listener opened", False), ("build (worldserver-daemon) ready...", True)):
            with self.subTest(output=output), patch.object(g1.subprocess, "run", return_value=
                    subprocess.CompletedProcess([], 0, output, "")) as process:
                self.assertEqual(g1.world_initialization_ready(self.state(), entry), ready)
                self.assertEqual(process.call_args.args[0], ["docker", "logs", "--since",
                    entry["State"]["StartedAt"], "coa-g1-test-worldserver"])

    def test_ordered_start_waits_for_world_before_starting_auth(self):
        events = []
        with patch.object(g1, "compose", side_effect=lambda root, *args: events.append(args)), \
                patch.object(g1, "wait_game", side_effect=lambda root, state, **kwargs:
                             events.append(("ready", kwargs.get("roles", ("authserver", "worldserver"))))), \
                patch.object(g1, "wait_realm", side_effect=lambda root, state: events.append(("realm-online",))):
            g1.start_game(self.root, self.state())
        self.assertEqual(events, [("start", "worldserver"), ("ready", ("worldserver",)),
                                  ("start", "authserver"), ("ready", ("authserver", "worldserver")), ("realm-online",)])

    def test_realm_timing_uses_bounded_native_configuration(self):
        (self.root / "etc").mkdir()
        world = self.root / "etc/worldserver.conf"
        auth = self.root / "etc/authserver.conf"
        world.write_text("# defaults\n", encoding="utf-8")
        auth.write_text("# defaults\n", encoding="utf-8")
        self.assertEqual(g1.realm_readiness_timing(self.root), (650, 20))
        world.write_text("UpdateUptimeInterval = 2\n", encoding="utf-8")
        auth.write_text("RealmsStateUpdateDelay = 5\n", encoding="utf-8")
        self.assertEqual(g1.realm_readiness_timing(self.root), (155, 5))
        for interval in (0, 16):
            world.write_text("UpdateUptimeInterval = " + str(interval) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "1-15 minutes"):
                g1.realm_readiness_timing(self.root)

    def test_realm_probe_is_read_only_and_scoped_to_owned_database(self):
        state = self.state()
        entry = {"Config": {"Labels": {g1.OWNER: state["id"]}}, "State": {"Running": True}}
        with patch.object(g1, "docker_inspect", return_value=entry), patch.object(g1.subprocess, "run", return_value=
                subprocess.CompletedProcess([], 0, "2\n", "")) as process:
            self.assertEqual(g1.realm_flags(state), 2)
        command = process.call_args.args[0]
        self.assertEqual(command[:3], ["docker", "exec", "coa-g1-test-database"])
        self.assertIn("SELECT flag FROM acore_auth.realmlist WHERE id = 1;", command[-1])
        self.assertNotIn("UPDATE", command[-1])
        entry["Config"]["Labels"][g1.OWNER] = "someone-else"
        with patch.object(g1, "docker_inspect", return_value=entry), patch.object(g1.subprocess, "run") as process, \
                self.assertRaisesRegex(RuntimeError, "ownership changed"):
            g1.realm_flags(state)
        process.assert_not_called()

    def test_realm_readiness_waits_for_native_online_state_and_auth_refresh(self):
        clock = [0]
        def advance(seconds):
            clock[0] += seconds
        with patch.object(g1, "realm_readiness_timing", return_value=(650, 20)), \
                patch.object(g1, "running_game_service"), patch.object(g1, "service_listener_ready", return_value=True), \
                patch.object(g1.socket, "create_connection"), \
                patch.object(g1, "realm_flags", side_effect=[3, 2, 0, 0, 0, 0, 0]) as flags, \
                patch.object(g1.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(g1.time, "sleep", side_effect=advance), patch("builtins.print"):
            g1.wait_realm(self.root, self.state())
        self.assertEqual(clock[0], 30)
        self.assertEqual(flags.call_count, 7)

    def test_realm_readiness_times_out_without_mutating_stuck_flags(self):
        clock = [0]
        def advance(seconds):
            clock[0] += seconds
        with patch.object(g1, "realm_readiness_timing", return_value=(10, 5)), \
                patch.object(g1, "running_game_service"), patch.object(g1, "service_listener_ready", return_value=True), \
                patch.object(g1.socket, "create_connection"), patch.object(g1, "realm_flags", return_value=2), \
                patch.object(g1.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(g1.time, "sleep", side_effect=advance), patch("builtins.print"), \
                self.assertRaisesRegex(RuntimeError, "remained offline"):
            g1.wait_realm(self.root, self.state())

    def test_unready_world_prevents_auth_start(self):
        with patch.object(g1, "compose") as compose, patch.object(g1, "wait_game", side_effect=RuntimeError("not ready")), \
                self.assertRaisesRegex(RuntimeError, "not ready"):
            g1.start_game(self.root, self.state())
        compose.assert_called_once_with(self.root, "start", "worldserver")

    def test_wait_game_fails_immediately_if_owned_service_exits(self):
        state = self.state()
        entry = {"Config": {"Labels": {g1.OWNER: state["id"]}}, "State": {"Running": False}, "RestartCount": 0}
        with patch.object(g1, "docker_inspect", return_value=entry), patch.object(g1.time, "sleep") as sleep, \
                self.assertRaisesRegex(RuntimeError, "exited"):
            g1.wait_game(self.root, state, roles=("worldserver",))
        sleep.assert_not_called()

    def test_manage_cleans_up_failed_ordered_start(self):
        state = {**self.state(), "phase": "ready", "compose_sha256": "verified"}
        args = SimpleNamespace(command="start", dir=str(self.root))
        with patch.object(g1, "prerequisites"), patch.object(g1, "owned", return_value=(self.root, state)), \
                patch.object(g1, "compose"), patch.object(g1, "wait_database"), \
                patch.object(g1, "start_game", side_effect=RuntimeError("start failed")), \
                patch.object(g1, "stop_failed_game") as cleanup, self.assertRaisesRegex(RuntimeError, "start failed"):
            g1.manage(args)
        cleanup.assert_called_once_with(self.root, state)

    def test_install_retains_failed_start_and_stops_its_game_services(self):
        target = self.root / "new-install"
        state = {**self.state(), "root": str(target), "phase": "planned", "release_id": "g1-test"}
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        args = SimpleNamespace(command="install", dry_run=False, manifest=self.manifest_path,
                               toolchain_image="test-toolchain", no_start=False, auth_port=33727)
        report = {"status": "passed", "stages": {name: {"status": "passed"} for name in ("source", "build", "unit")}}
        with patch.object(g1, "preflight", return_value=(state, self.manifest)), patch.object(g1, "prepare_sources"), \
                patch.object(g1, "docker_inspect", return_value={"Id": "test-toolchain"}), \
                patch.object(g1, "executor"), patch.object(g1, "load", return_value=report), \
                patch.object(g1, "digest", return_value="d" * 64), patch.object(g1, "composition", return_value={}), \
                patch.object(g1, "absent_resources"), patch.object(g1, "ports_available"), \
                patch.object(g1, "compose"), patch.object(g1, "run"), patch.object(g1, "wait_database"), \
                patch.object(g1, "start_game", side_effect=RuntimeError("start failed")), \
                patch.object(g1, "stop_failed_game") as cleanup, patch("builtins.print"), \
                self.assertRaisesRegex(RuntimeError, "start failed"):
            g1.install(args)
        cleanup.assert_called_once_with(target, state)
        retained = json.loads((target / "installation.json").read_text(encoding="utf-8"))
        self.assertEqual(retained["phase"], "incomplete")
        self.assertEqual(retained["failed_phase"], "ready")
        self.assertTrue((target / "compose.json").is_file())

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

    def test_runtime_worldforged_keeps_placement_migrations_excluded(self):
        self.manifest["migration_modules"] = list(self.manifest["modules"])
        self.manifest["modules"].append("mod-worldforged-pickups")
        self.manifest["settings"] = {"worldserver.conf": {"Visibility.ObjectSparkles": "1"}}
        for relative in ("worldserver.conf.dist", "authserver.conf.dist", "modules/playerbots.conf.dist"):
            path = self.root / "etc" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Updates.EnableDatabases = 7\n", encoding="utf-8")
        with patch.object(container, "ROOT", self.root):
            container.runtime_configuration({**self.state(), "bots": 1000}, self.manifest, "e" * 64)
        expected = 'Updates.AllowedModules = "' + ",".join(self.manifest["migration_modules"]) + '"'
        for relative in ("worldserver.conf", "authserver.conf"):
            text = (self.root / "etc" / relative).read_text(encoding="utf-8")
            self.assertIn(expected, text)
            self.assertNotIn("mod-worldforged-pickups", text)
            self.assertIn("Updates.EnableDatabases = 0", text)
        self.assertIn("Visibility.ObjectSparkles = 1",
                      (self.root / "etc/worldserver.conf").read_text(encoding="utf-8"))

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
            container.import_character_schema(self.manifest)
        self.assertEqual(database.call_count, 1)

    def test_character_dependency_follows_complete_base_and_records_identity(self):
        base = self.root / "data/sql/base/db_characters"
        base.mkdir(parents=True)
        for name in ("characters.sql", "updates.sql"):
            (base / name).write_text("SELECT 1;", encoding="utf-8")
        dependencies = [self.root / "modules/schema.sql", self.root / "modules/required.sql"]
        dependencies[0].parent.mkdir()
        for dependency in dependencies:
            dependency.write_text("CREATE TABLE " + dependency.stem + "(guid INT);", encoding="utf-8")
        imported = []
        def database(query=None, schema=None, file=None):
            if file:
                imported.append(file)
                return ""
            if query.startswith("SELECT COLUMN_TYPE"):
                return "enum('RELEASED','MODULE','ARCHIVED')"
            if query.startswith("SELECT CONCAT"):
                dependency = next(path for path in dependencies if path.name in query)
                return container.digest(dependency, "sha1") + ":MODULE"
            return "0"
        with patch.object(container, "SOURCE", self.root), patch.object(container, "mysql", side_effect=database), \
                patch.object(container, "character_schema_dependencies", return_value={
                    "modules/" + path.name: container.digest(path) for path in dependencies}):
            result = container.import_character_schema(self.manifest)
        self.assertEqual(imported, [base / "characters.sql", base / "updates.sql", *dependencies])
        for dependency in dependencies:
            self.assertEqual(result["dependencies"][dependency.name]["sha1"], container.digest(dependency, "sha1"))
            self.assertEqual(result["dependencies"][dependency.name]["state"], "MODULE")

    def test_character_dependency_changes_fail_before_importing_base(self):
        dependency = self.root / "schema.sql"
        dependency.write_text("unexpected schema", encoding="utf-8")
        with patch.object(container, "SOURCE", self.root), patch.object(container, "mysql", return_value="0") as database, \
                patch.object(container, "character_schema_dependencies", return_value={"schema.sql": "0" * 64}), \
                self.assertRaisesRegex(RuntimeError, "schema dependency changed"):
            container.import_character_schema(self.manifest)
        self.assertEqual(database.call_count, 1)

    def test_character_dependencies_reject_unreviewed_revision(self):
        with self.assertRaisesRegex(RuntimeError, "not been reviewed"):
            container.character_schema_dependencies(self.manifest)

    def test_release_dependencies_preserve_old_bootstrap_and_supply_new_core_schema(self):
        old = json.loads((REPO / "releases/g1-20261029/manifest.json").read_text(encoding="utf-8"))
        current = json.loads((REPO / "releases/g1-20261118/manifest.json").read_text(encoding="utf-8"))
        original = container.character_schema_dependencies(old)
        expanded = container.character_schema_dependencies(current)
        self.assertEqual(original, container.CHARACTER_SCHEMA_DEPENDENCIES)
        self.assertEqual(expanded, {**original,
            "modules/mod-coa-challenges/data/sql/db-characters/2026_09_16_00_mod_coa_challenges.sql":
                "2244f9a53713cc3686c3cd4a31ebf761cb210ecdc01859fb5df80887d344d4c2"})
        for manifest in (old, current):
            self.assertNotIn("mod-coa-challenges", manifest["modules"])
            self.assertNotIn("mod-coa-challenges", container.migration_modules(manifest))
            self.assertNotIn("mod-worldforged-pickups", container.migration_modules(manifest))

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
        for name in ("g1-20261029", "g1-20261118"):
            with self.subTest(release=name):
                self.assertEqual(g1.release(REPO / "releases" / name / "manifest.json")["release_id"], name)

    def test_default_release_is_current_worldforged_recipe(self):
        args = g1.parser().parse_args(["check", "--dir", "/new-runtime", "--data-dir", "/provided-data"])
        self.assertEqual(args.manifest, REPO / "releases/g1-20261118/manifest.json")


if __name__ == "__main__":
    unittest.main()
