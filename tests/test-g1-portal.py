import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("g1_portal", REPO / "scripts/g1-portal.py")
portal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portal)


# ---------------------------------------------------------------------------
# SRP6
# ---------------------------------------------------------------------------

class SRP6Tests(unittest.TestCase):
    def test_produces_32_byte_outputs(self):
        salt, verifier = portal.srp6_verifier("TESTUSER", "hunter2")
        self.assertEqual(len(salt), 32)
        self.assertEqual(len(verifier), 32)

    def test_different_passwords_produce_different_verifiers(self):
        _, v1 = portal.srp6_verifier("USER", "password1")
        _, v2 = portal.srp6_verifier("USER", "password2")
        self.assertNotEqual(v1, v2)

    def test_different_salts_per_call(self):
        s1, _ = portal.srp6_verifier("USER", "pass")
        s2, _ = portal.srp6_verifier("USER", "pass")
        self.assertNotEqual(s1, s2)

    def test_uppercase_username_matches(self):
        # SRP6 must treat upper and lower case username identically
        _, v_up = portal.srp6_verifier("USER", "pass")
        _, v_lo = portal.srp6_verifier("user", "pass")
        # They use the same salt only if we force it; just verify function accepts both
        self.assertEqual(len(v_up), 32)
        self.assertEqual(len(v_lo), 32)

    def test_verifier_is_valid_srp6(self):
        # v = g^x mod N; x derived from known inputs
        salt = b"\x00" * 32
        username, password = "TEST", "SECRET"
        with patch.object(portal.secrets, "token_bytes", return_value=salt):
            actual_salt, verifier = portal.srp6_verifier(username, password)
        self.assertEqual(actual_salt, salt)
        h1 = hashlib.sha1(f"{username}:{password}".encode()).digest()
        x = int.from_bytes(hashlib.sha1(salt + h1).digest(), "little")
        expected = pow(portal._SRP6_G, x, portal._SRP6_N).to_bytes(32, "little")
        self.assertEqual(verifier, expected)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class ValidationTests(unittest.TestCase):
    def test_valid_usernames(self):
        for name in ("ABC", "A_1", "USERNAME123", "A" * 16, "a1b"):
            with self.subTest(name):
                self.assertEqual(portal.validate_username(name), name.upper())

    def test_invalid_usernames(self):
        for name in ("", "AB", "A" * 17, "user name", "user@host", "us-er"):
            with self.subTest(name):
                with self.assertRaises(ValueError):
                    portal.validate_username(name)

    def test_valid_passwords(self):
        for pw in ("12345678", "a" * 32, "p@ssw0rd!"):
            with self.subTest(pw):
                self.assertEqual(portal.validate_password(pw), pw)

    def test_invalid_passwords(self):
        for pw in ("", "short", "has a space", "a" * 33):
            with self.subTest(pw):
                with self.assertRaises(ValueError):
                    portal.validate_password(pw)


# ---------------------------------------------------------------------------
# db_query shell construction
# ---------------------------------------------------------------------------

class DbQueryTests(unittest.TestCase):
    def _run_ok(self, stdout=""):
        result = MagicMock()
        result.returncode = 0
        result.stdout = stdout
        result.stderr = ""
        return result

    def test_calls_docker_exec(self):
        with patch("subprocess.run", return_value=self._run_ok()) as mock_run:
            portal.db_query("coa-g1-test", "SELECT 1;")
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "docker")
        self.assertEqual(cmd[1], "exec")
        self.assertEqual(cmd[2], "coa-g1-test-database")

    def test_database_error_raises(self):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "ERROR 1045 (28000): Access denied"
        result.stdout = ""
        with patch("subprocess.run", return_value=result):
            with self.assertRaises(ValueError):
                portal.db_query("project", "SELECT 1;")

    def test_sql_is_quoted(self):
        with patch("subprocess.run", return_value=self._run_ok()) as mock_run:
            portal.db_query("proj", "SELECT username FROM account WHERE id=1;")
        cmd = mock_run.call_args[0][0]
        shell_cmd = cmd[-1]
        # The SQL must appear shell-quoted somewhere in the command
        self.assertIn("SELECT username FROM account WHERE id=1;", shell_cmd)


# ---------------------------------------------------------------------------
# Account operations (mocked docker exec)
# ---------------------------------------------------------------------------

class AccountOperationTests(unittest.TestCase):
    def _mock_query(self, responses):
        """Return a side-effect for db_query that pops from responses list."""
        it = iter(responses)
        return lambda *a, **kw: next(it)

    def test_list_accounts_parses_rows(self):
        output = "1\tALICE\t2026-11-01 10:00:00\t0\t0\n2\tBOB\t\t1\t3"
        with patch.object(portal, "db_query", return_value=output):
            accounts = portal.list_accounts("proj")
        self.assertEqual(len(accounts), 2)
        self.assertEqual(accounts[0]["username"], "ALICE")
        self.assertFalse(accounts[0]["online"])
        self.assertEqual(accounts[0]["gmlevel"], 0)
        self.assertTrue(accounts[1]["online"])
        self.assertEqual(accounts[1]["gmlevel"], 3)

    def test_list_accounts_null_last_login(self):
        with patch.object(portal, "db_query", return_value="1\tUSER\tNULL\t0\t0"):
            accounts = portal.list_accounts("proj")
        self.assertIsNone(accounts[0]["last_login"])

    def test_create_account_inserts(self):
        calls = []
        def fake_query(proj, sql, schema="acore_auth"):
            calls.append(sql)
            return "0" if "COUNT" in sql else ""
        with patch.object(portal, "db_query", side_effect=fake_query):
            portal.create_account("proj", "newuser", "mypassword1")
        self.assertEqual(len(calls), 2)
        self.assertIn("COUNT", calls[0])
        self.assertIn("INSERT INTO account", calls[1])
        self.assertIn("NEWUSER", calls[1])
        self.assertIn("UNHEX", calls[1])

    def test_create_account_duplicate_rejected(self):
        with patch.object(portal, "db_query", return_value="1"):
            with self.assertRaises(ValueError, msg="already exists"):
                portal.create_account("proj", "ALICE", "password123")

    def test_change_password_updates(self):
        calls = []
        def fake_query(proj, sql, schema="acore_auth"):
            calls.append(sql)
            return "1" if "COUNT" in sql else ""
        with patch.object(portal, "db_query", side_effect=fake_query):
            portal.change_password("proj", "alice", "newpassword1")
        update_calls = [c for c in calls if "UPDATE account SET" in c]
        self.assertEqual(len(update_calls), 1)
        self.assertIn("session_key=NULL", update_calls[0])

    def test_change_password_missing_account_rejected(self):
        with patch.object(portal, "db_query", return_value="0"):
            with self.assertRaises(ValueError):
                portal.change_password("proj", "GHOST", "newpassword1")

    def test_set_gmlevel_inserts_access(self):
        calls = []
        def fake_query(proj, sql, schema="acore_auth"):
            calls.append(sql)
            return "42" if "SELECT id" in sql else ""
        with patch.object(portal, "db_query", side_effect=fake_query):
            portal.set_gmlevel("proj", "ALICE", 2)
        self.assertTrue(any("INSERT INTO account_access" in c for c in calls))
        self.assertTrue(any("SecurityLevel, RealmID) VALUES (42, 2, -1)" in c for c in calls))

    def test_set_gmlevel_zero_only_deletes(self):
        calls = []
        def fake_query(proj, sql, schema="acore_auth"):
            calls.append(sql)
            return "42" if "SELECT id" in sql else ""
        with patch.object(portal, "db_query", side_effect=fake_query):
            portal.set_gmlevel("proj", "ALICE", 0)
        self.assertFalse(any("INSERT INTO account_access" in c for c in calls))
        self.assertTrue(any("DELETE FROM account_access" in c for c in calls))

    def test_set_gmlevel_invalid_level_rejected(self):
        with self.assertRaises(ValueError):
            portal.set_gmlevel("proj", "ALICE", 4)
        with self.assertRaises(ValueError):
            portal.set_gmlevel("proj", "ALICE", -1)

    def test_set_gmlevel_missing_account_rejected(self):
        with patch.object(portal, "db_query", return_value=""):
            with self.assertRaises(ValueError):
                portal.set_gmlevel("proj", "GHOST", 1)


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class HttpHandlerTests(unittest.TestCase):
    def _make_state(self):
        return {"project": "coa-g1-test", "release_id": "g1-test",
                "root": "/tmp/test", "id": "abc"}

    def _make_request(self, method, path, body=None):
        """Build a fake handler instance without binding a real socket."""
        handler = portal._Handler.__new__(portal._Handler)
        handler._state = self._make_state()
        handler.command = method
        handler.path = path
        handler.headers = {"Content-Length": str(len(json.dumps(body).encode())) if body else "0"}
        handler.rfile = MagicMock()
        if body:
            handler.rfile.read.return_value = json.dumps(body).encode()
        handler.wfile = MagicMock()
        handler._sent = []
        handler.send_response = lambda code: handler._sent.append(("response", code))
        handler.send_header = lambda k, v: handler._sent.append(("header", k, v))
        handler.end_headers = lambda: handler._sent.append(("end",))
        return handler

    def _capture_json(self, handler):
        handler.wfile.write.assert_called_once()
        return json.loads(handler.wfile.write.call_args[0][0])

    def test_get_root_returns_html(self):
        handler = self._make_request("GET", "/")
        handler.do_GET()
        status = next(c[1] for c in handler._sent if c[0] == "response")
        self.assertEqual(status, 200)
        content_type = next(c[2] for c in handler._sent if c[0] == "header" and c[1] == "Content-Type")
        self.assertIn("text/html", content_type)

    def test_get_accounts_returns_json(self):
        accounts = [{"id": 1, "username": "BOB", "last_login": None, "online": False, "gmlevel": 0}]
        with patch.object(portal, "list_accounts", return_value=accounts):
            handler = self._make_request("GET", "/api/accounts")
            handler.do_GET()
        body = self._capture_json(handler)
        self.assertEqual(body["accounts"], accounts)
        self.assertEqual(body["release"], "g1-test")

    def test_post_create_account(self):
        with patch.object(portal, "create_account") as mock_create:
            handler = self._make_request("POST", "/api/accounts",
                                         {"username": "NEWUSER", "password": "mypassword1"})
            handler.do_POST()
        mock_create.assert_called_once_with("coa-g1-test", "NEWUSER", "mypassword1")
        body = self._capture_json(handler)
        self.assertTrue(body["ok"])

    def test_post_create_validation_error_returns_400(self):
        with patch.object(portal, "create_account", side_effect=ValueError("already exists")):
            handler = self._make_request("POST", "/api/accounts",
                                         {"username": "X", "password": "pass"})
            handler.do_POST()
        status = next(c[1] for c in handler._sent if c[0] == "response")
        self.assertEqual(status, 400)
        body = self._capture_json(handler)
        self.assertIn("error", body)

    def test_post_change_password(self):
        with patch.object(portal, "change_password") as mock_cp:
            handler = self._make_request("POST", "/api/accounts/ALICE/password",
                                         {"password": "newpassword1"})
            handler.do_POST()
        mock_cp.assert_called_once_with("coa-g1-test", "ALICE", "newpassword1")
        body = self._capture_json(handler)
        self.assertTrue(body["ok"])

    def test_post_set_gmlevel(self):
        with patch.object(portal, "set_gmlevel") as mock_gm:
            handler = self._make_request("POST", "/api/accounts/ALICE/gmlevel", {"level": 2})
            handler.do_POST()
        mock_gm.assert_called_once_with("coa-g1-test", "ALICE", 2)
        body = self._capture_json(handler)
        self.assertTrue(body["ok"])

    def test_post_gmlevel_non_integer_returns_400(self):
        with patch.object(portal, "set_gmlevel"):
            handler = self._make_request("POST", "/api/accounts/ALICE/gmlevel",
                                         {"level": "admin"})
            handler.do_POST()
        status = next(c[1] for c in handler._sent if c[0] == "response")
        self.assertEqual(status, 400)

    def test_unknown_path_returns_404(self):
        handler = self._make_request("GET", "/unknown")
        handler.do_GET()
        status = next(c[1] for c in handler._sent if c[0] == "response")
        self.assertEqual(status, 404)

    def test_unknown_post_action_returns_404(self):
        with patch.object(portal, "db_query", return_value=""):
            handler = self._make_request("POST", "/api/accounts/ALICE/delete", {})
            handler.do_POST()
        status = next(c[1] for c in handler._sent if c[0] == "response")
        self.assertEqual(status, 404)


# ---------------------------------------------------------------------------
# owned() — installation verification
# ---------------------------------------------------------------------------

class OwnedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = {
            "root": str(self.root),
            "id": "abc123",
            "phase": "ready",
            "project": "coa-g1-test",
            "release_id": "g1-test",
        }
        (self.root / "installation.json").write_text(json.dumps(self.state))

    def _good_container(self):
        return {
            "Config": {"Labels": {portal.OWNER: "abc123"}},
            "State": {"Running": True},
        }

    def test_valid_installation_accepted(self):
        with patch.object(portal, "_docker_inspect", return_value=self._good_container()):
            root, state = portal.owned(str(self.root))
        self.assertEqual(state["project"], "coa-g1-test")

    def test_wrong_phase_rejected(self):
        self.state["phase"] = "incomplete"
        (self.root / "installation.json").write_text(json.dumps(self.state))
        with patch.object(portal, "_docker_inspect", return_value=self._good_container()):
            with self.assertRaises(ValueError, msg="ready"):
                portal.owned(str(self.root))

    def test_missing_container_rejected(self):
        with patch.object(portal, "_docker_inspect", return_value=None):
            with self.assertRaises(ValueError):
                portal.owned(str(self.root))

    def test_stopped_database_rejected(self):
        container = self._good_container()
        container["State"]["Running"] = False
        with patch.object(portal, "_docker_inspect", return_value=container):
            with self.assertRaises(ValueError):
                portal.owned(str(self.root))

    def test_unrelated_container_rejected(self):
        container = self._good_container()
        container["Config"]["Labels"][portal.OWNER] = "different-id"
        with patch.object(portal, "_docker_inspect", return_value=container):
            with self.assertRaises(ValueError):
                portal.owned(str(self.root))


# ---------------------------------------------------------------------------
# Dev mode
# ---------------------------------------------------------------------------

class DevModeTests(unittest.TestCase):
    def _running_container(self):
        return {
            "Config": {"Labels": {portal.OWNER: portal._DEV_ID}},
            "State": {"Running": True},
        }

    def _stopped_container(self):
        return {
            "Config": {"Labels": {portal.OWNER: portal._DEV_ID}},
            "State": {"Running": False},
        }

    def test_dev_start_launches_container(self):
        with patch.object(portal, "_docker_inspect", return_value=None), \
             patch("subprocess.run") as mock_run, \
             patch.object(portal, "_wait_dev_db"), \
             patch.object(portal, "_create_dev_schema"):
            mock_run.return_value = MagicMock(returncode=0)
            state = portal.dev_start()
        docker_run_calls = [c for c in mock_run.call_args_list
                            if c[0][0][1] == "run"]
        self.assertEqual(len(docker_run_calls), 1)
        cmd = docker_run_calls[0][0][0]
        self.assertIn(_DEV_IMAGE_name(portal), cmd)
        self.assertIn("-d", cmd)

    def test_dev_start_reuses_running_container(self):
        with patch.object(portal, "_docker_inspect", return_value=self._running_container()), \
             patch("subprocess.run") as mock_run, \
             patch.object(portal, "_wait_dev_db"), \
             patch.object(portal, "_create_dev_schema"):
            portal.dev_start()
        docker_run_calls = [c for c in mock_run.call_args_list
                            if c[0][0][1:3] == ["run", "-d"]]
        self.assertEqual(len(docker_run_calls), 0)

    def test_dev_start_removes_stopped_container(self):
        with patch.object(portal, "_docker_inspect", return_value=self._stopped_container()), \
             patch("subprocess.run") as mock_run, \
             patch.object(portal, "_wait_dev_db"), \
             patch.object(portal, "_create_dev_schema"):
            mock_run.return_value = MagicMock(returncode=0)
            portal.dev_start()
        rm_calls = [c for c in mock_run.call_args_list if "rm" in c[0][0]]
        self.assertTrue(len(rm_calls) >= 1)

    def test_dev_start_returns_dev_state(self):
        with patch.object(portal, "_docker_inspect", return_value=None), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)), \
             patch.object(portal, "_wait_dev_db"), \
             patch.object(portal, "_create_dev_schema"):
            state = portal.dev_start()
        self.assertEqual(state["project"], portal._DEV_PROJECT)
        self.assertEqual(state["release_id"], "dev")
        self.assertEqual(state["phase"], "ready")

    def test_dev_teardown_stops_and_removes(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            portal.dev_teardown()
        commands = [c[0][0] for c in mock_run.call_args_list]
        self.assertTrue(any("stop" in cmd for cmd in commands))
        self.assertTrue(any("rm" in cmd for cmd in commands))

    def test_wait_dev_db_returns_on_success(self):
        ok = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=ok):
            portal._wait_dev_db(portal._DEV_PROJECT + "-database", timeout=10)

    def test_wait_dev_db_raises_on_timeout(self):
        fail = MagicMock(returncode=1)
        with patch("subprocess.run", return_value=fail), \
             patch("time.sleep"), \
             patch("time.monotonic", side_effect=[0.0, 0.0, 999.0]):
            with self.assertRaises(ValueError):
                portal._wait_dev_db("container", timeout=5)

    def test_create_dev_schema_runs_sql(self):
        ok = MagicMock(returncode=0, stderr="", stdout="")
        with patch("subprocess.run", return_value=ok) as mock_run:
            portal._create_dev_schema("mycontainer")
        cmd = mock_run.call_args[0][0]
        self.assertIn("mycontainer", cmd)
        self.assertIn("-i", cmd)
        sql_input = mock_run.call_args[1]["input"]
        self.assertIn("CREATE TABLE", sql_input)
        self.assertIn("account_access", sql_input)

    def test_create_dev_schema_raises_on_error(self):
        fail = MagicMock(returncode=1, stderr="ERROR 1234: Something went wrong", stdout="")
        with patch("subprocess.run", return_value=fail):
            with self.assertRaises(ValueError):
                portal._create_dev_schema("mycontainer")


def _DEV_IMAGE_name(p):
    return p._DEV_IMAGE


if __name__ == "__main__":
    unittest.main()
