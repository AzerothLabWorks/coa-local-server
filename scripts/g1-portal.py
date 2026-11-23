#!/usr/bin/env python3
"""Local account management web UI for a G1 CoA installation."""

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
import secrets
import shlex
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path


OWNER = "org.azerothlabworks.g1.installation"

# WoW WotLK SRP6 parameters; N stored little-endian as it appears in the DB.
_SRP6_N = int.from_bytes(
    bytes.fromhex("B79BE3A87228C3AB8F5EBFBF8B180108530506298B8BBDAD5B53E1895E644B89"),
    "little",
)
_SRP6_G = 7

_USERNAME_RE = re.compile(r"[A-Z0-9_]{3,16}\Z")
_ACCOUNT_PATH_RE = re.compile(r"/api/accounts/([A-Z0-9_]{3,16})/(\w+)\Z")

_DEV_PROJECT = "coa-g1-portal-dev"
_DEV_ID = "devmode0000000000000000000000000"
_DEV_IMAGE = "mysql:8.4"
_DEV_PASSWORD = "devpassword"

_DEV_SCHEMA = """
CREATE DATABASE IF NOT EXISTS acore_auth;
CREATE TABLE IF NOT EXISTS acore_auth.account (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(32) NOT NULL DEFAULT '',
  salt BINARY(32) NOT NULL,
  verifier BINARY(32) NOT NULL,
  session_key BINARY(40) DEFAULT NULL,
  token_key VARCHAR(100) NOT NULL DEFAULT '',
  email VARCHAR(255) NOT NULL DEFAULT '',
  reg_mail VARCHAR(255) NOT NULL DEFAULT '',
  joindate TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_ip VARCHAR(15) NOT NULL DEFAULT '127.0.0.1',
  failed_logins INT UNSIGNED NOT NULL DEFAULT 0,
  locked TINYINT UNSIGNED NOT NULL DEFAULT 0,
  locked_country VARCHAR(2) NOT NULL DEFAULT '',
  last_login TIMESTAMP DEFAULT NULL,
  online TINYINT UNSIGNED NOT NULL DEFAULT 0,
  expansion TINYINT UNSIGNED NOT NULL DEFAULT 2,
  mutetime BIGINT NOT NULL DEFAULT 0,
  muteflags TINYINT UNSIGNED NOT NULL DEFAULT 0,
  mutereason VARCHAR(255) NOT NULL DEFAULT '',
  muteby VARCHAR(50) NOT NULL DEFAULT '',
  locale TINYINT UNSIGNED NOT NULL DEFAULT 0,
  os VARCHAR(4) NOT NULL DEFAULT '',
  totaltime INT UNSIGNED NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS acore_auth.account_access (
  AccountID INT UNSIGNED NOT NULL DEFAULT 0,
  SecurityLevel TINYINT NOT NULL DEFAULT 0,
  RealmID INT NOT NULL DEFAULT -1,
  PRIMARY KEY (AccountID, RealmID)
);
"""


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_username(raw):
    value = raw.strip().upper()
    _require(_USERNAME_RE.fullmatch(value),
             "Username must be 3–16 characters: letters, digits, underscore only")
    return value


def validate_password(raw):
    _require(raw and len(raw) >= 8, "Password must be at least 8 characters")
    _require(len(raw) <= 32, "Password must be at most 32 characters")
    _require(" " not in raw, "Password must not contain spaces")
    return raw


# ---------------------------------------------------------------------------
# SRP6
# ---------------------------------------------------------------------------

def srp6_verifier(username, password):
    """Return (salt, verifier) as 32-byte values stored in little-endian order."""
    salt = secrets.token_bytes(32)
    h1 = hashlib.sha1(f"{username.upper()}:{password.upper()}".encode()).digest()
    x = int.from_bytes(hashlib.sha1(salt + h1).digest(), "little")
    verifier = pow(_SRP6_G, x, _SRP6_N).to_bytes(32, "little")
    return salt, verifier


# ---------------------------------------------------------------------------
# Installation state
# ---------------------------------------------------------------------------

def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _docker_inspect(kind, name):
    result = subprocess.run(["docker", kind, "inspect", name],
                            capture_output=True, text=True)
    if result.returncode:
        return None
    return json.loads(result.stdout)[0]


def owned(directory):
    """Return (root, state) after verifying the installation is owned and the DB is up."""
    root = Path(directory).expanduser().absolute()
    try:
        state = _load(root / "installation.json")
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Could not read installation.json: " + str(exc)) from exc
    _require(state.get("root") == str(root), "Installation root path mismatch")
    _require(state.get("phase") == "ready", "Installation is not in a ready state")
    db_name = state["project"] + "-database"
    item = _docker_inspect("container", db_name)
    _require(item is not None, f"Database container '{db_name}' not found; is the server running?")
    labels = (item.get("Config") or {}).get("Labels") or {}
    _require(labels.get(OWNER) == state["id"],
             f"Container '{db_name}' is not owned by this installation")
    _require(item["State"].get("Running"),
             f"Database container '{db_name}' is not running; start the server first")
    return root, state


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def db_query(project, sql, schema="acore_auth"):
    """Run SQL in the database container and return stripped stdout."""
    inner = (
        "export MYSQL_PWD=\"$MYSQL_ROOT_PASSWORD\"; "
        "exec mysql --no-defaults --no-login-paths --user=root "
        "--batch --skip-column-names --execute " + shlex.quote(sql) + " " + schema
    )
    result = subprocess.run(
        ["docker", "exec", project + "-database", "sh", "-c", inner],
        capture_output=True, text=True, timeout=15,
    )
    _require(result.returncode == 0,
             "Database error: " + result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown")
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Account operations
# ---------------------------------------------------------------------------

def list_accounts(project):
    """Return a list of account dicts ordered by id."""
    output = db_query(project,
        "SELECT a.id, a.username, COALESCE(a.last_login, ''), a.online, "
        "COALESCE(aa.SecurityLevel, 0) "
        "FROM account a "
        "LEFT JOIN account_access aa ON a.id = aa.AccountID AND aa.RealmID = -1 "
        "ORDER BY a.id;")
    accounts = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) == 5:
            accounts.append({
                "id": int(parts[0]),
                "username": parts[1],
                "last_login": parts[2] if parts[2] not in ("NULL", "") else None,
                "online": parts[3] == "1",
                "gmlevel": int(parts[4]) if parts[4].lstrip("-").isdigit() else 0,
            })
    return accounts


def create_account(project, username, password):
    """Create a new player account with WotLK expansion (addon level 2)."""
    username = validate_username(username)
    password = validate_password(password)
    count = db_query(project, f"SELECT COUNT(*) FROM account WHERE username='{username}';")
    _require(count.strip() == "0", f"Account '{username}' already exists")
    salt, verifier = srp6_verifier(username, password)
    s, v = salt.hex().upper(), verifier.hex().upper()
    db_query(project,
        f"INSERT INTO account "
        f"(username, salt, verifier, email, reg_mail, joindate, last_ip, "
        f"failed_logins, locked, locked_country, last_login, online, expansion, "
        f"mutetime, muteflags, mutereason, muteby, locale, os, totaltime) "
        f"VALUES ('{username}', UNHEX('{s}'), UNHEX('{v}'), "
        f"'', '', NOW(), '127.0.0.1', 0, 0, '', NOW(), 0, 2, 0, 0, '', '', 0, '', 0);")


def change_password(project, username, password):
    """Replace a player's SRP6 credentials and invalidate any active session."""
    username = validate_username(username)
    password = validate_password(password)
    count = db_query(project, f"SELECT COUNT(*) FROM account WHERE username='{username}';")
    _require(count.strip() == "1", f"Account '{username}' not found")
    salt, verifier = srp6_verifier(username, password)
    s, v = salt.hex().upper(), verifier.hex().upper()
    db_query(project,
        f"UPDATE account SET salt=UNHEX('{s}'), verifier=UNHEX('{v}'), "
        f"session_key=NULL WHERE username='{username}';")


def set_gmlevel(project, username, level):
    """Set or clear the GM security level for an account across all realms."""
    username = validate_username(username)
    _require(isinstance(level, int) and 0 <= level <= 3, "GM level must be 0–3")
    result = db_query(project,
        f"SELECT id FROM account WHERE username='{username}';")
    lines = [l for l in result.strip().splitlines() if l.isdigit()]
    _require(len(lines) == 1, f"Account '{username}' not found")
    account_id = int(lines[0])
    db_query(project,
        f"DELETE FROM account_access WHERE AccountID={account_id} AND RealmID=-1;")
    if level > 0:
        db_query(project,
            f"INSERT INTO account_access (AccountID, SecurityLevel, RealmID) "
            f"VALUES ({account_id}, {level}, -1);")


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CoA Account Manager</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}
header{background:#161b22;border-bottom:1px solid #30363d;padding:.9rem 1.5rem;display:flex;align-items:center;gap:1rem}
header h1{color:#f0883e;font-size:1.1rem;letter-spacing:.04em}
header small{color:#8b949e;font-size:.82rem}
main{max-width:860px;margin:1.75rem auto;padding:0 1rem}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1.25rem;margin-bottom:1.25rem}
.card h2{color:#58a6ff;font-size:.8rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:1rem}
.row{display:flex;gap:.75rem}
.row>*{flex:1}
label{display:block;font-size:.8rem;color:#8b949e;margin-bottom:.3rem}
input[type=text],input[type=password],select{
  width:100%;padding:.45rem .65rem;background:#0d1117;border:1px solid #30363d;
  border-radius:6px;color:#c9d1d9;font-size:.9rem;margin-bottom:.65rem;outline:none
}
input:focus,select:focus{border-color:#58a6ff}
.btn{padding:.42rem 1rem;border:none;border-radius:6px;cursor:pointer;font-size:.85rem;font-weight:600;transition:opacity .15s}
.btn:hover{opacity:.8}
.btn-primary{background:#238636;color:#fff}
.btn-sm{padding:.25rem .6rem;font-size:.78rem}
.btn-secondary{background:#21262d;color:#c9d1d9;border:1px solid #30363d}
.msg{padding:.45rem .7rem;border-radius:6px;margin-top:.6rem;font-size:.85rem;display:none}
.msg.ok{background:#1a3a1f;color:#3fb950;border:1px solid #3fb950}
.msg.err{background:#3a1414;color:#f85149;border:1px solid #f85149}
table{width:100%;border-collapse:collapse}
th,td{padding:.5rem .65rem;text-align:left;border-bottom:1px solid #21262d;font-size:.87rem}
th{color:#8b949e;font-size:.75rem;text-transform:uppercase;letter-spacing:.06em}
tr:last-child td{border-bottom:none}
.online{color:#3fb950}
.offline{color:#484f58}
.gm{color:#e3b341}
.acts{display:flex;gap:.35rem}
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:50;align-items:center;justify-content:center}
.modal-bg.open{display:flex}
.modal{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:1.4rem;min-width:300px;max-width:380px;width:100%}
.modal h3{color:#58a6ff;font-size:.95rem;margin-bottom:1rem}
.modal-footer{display:flex;gap:.5rem;justify-content:flex-end;margin-top:.75rem}
.refresh{float:right;margin-top:-2px}
</style>
</head>
<body>
<header>
  <h1>CoA Account Manager</h1>
  <small id="realm-info">connecting…</small>
</header>
<main>
  <div class="card">
    <h2>Create Account</h2>
    <div class="row">
      <div><label>Username</label><input type="text" id="new-user" placeholder="e.g. MYCHAR" autocomplete="off" spellcheck="false"></div>
      <div><label>Password</label><input type="password" id="new-pass" placeholder="8–32 characters" autocomplete="new-password"></div>
    </div>
    <button class="btn btn-primary" onclick="createAccount()">Create Account</button>
    <div id="create-msg" class="msg"></div>
  </div>
  <div class="card">
    <h2>Accounts <button class="btn btn-secondary btn-sm refresh" onclick="loadAccounts()">↻ Refresh</button></h2>
    <table>
      <thead><tr><th>ID</th><th>Username</th><th>Last Login</th><th>Status</th><th>GM Level</th><th>Actions</th></tr></thead>
      <tbody id="tbl"><tr><td colspan="6" style="color:#484f58">Loading…</td></tr></tbody>
    </table>
  </div>
</main>

<div class="modal-bg" id="pw-modal">
  <div class="modal">
    <h3>Change Password</h3>
    <input type="hidden" id="pw-user">
    <label>New Password</label>
    <input type="password" id="pw-new" placeholder="8–32 characters" autocomplete="new-password">
    <div id="pw-msg" class="msg"></div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="close_modal('pw-modal')">Cancel</button>
      <button class="btn btn-primary" onclick="submit_password()">Save</button>
    </div>
  </div>
</div>

<div class="modal-bg" id="gm-modal">
  <div class="modal">
    <h3>Set GM Level — <span id="gm-label" style="color:#c9d1d9"></span></h3>
    <input type="hidden" id="gm-user">
    <label>Security Level</label>
    <select id="gm-level">
      <option value="0">0 — Player</option>
      <option value="1">1 — Moderator</option>
      <option value="2">2 — Game Master</option>
      <option value="3">3 — Administrator</option>
    </select>
    <div id="gm-msg" class="msg"></div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="close_modal('gm-modal')">Cancel</button>
      <button class="btn btn-primary" onclick="submit_gmlevel()">Save</button>
    </div>
  </div>
</div>

<script>
async function api(method, path, body) {
  const opts = { method, headers: {'Content-Type': 'application/json'} };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({ error: 'Invalid response' }));
  if (!r.ok) throw new Error(j.error || 'Request failed (' + r.status + ')');
  return j;
}

function msg(id, text, ok) {
  const el = document.getElementById(id);
  el.textContent = text; el.className = 'msg ' + (ok ? 'ok' : 'err'); el.style.display = 'block';
}

async function loadAccounts() {
  try {
    const d = await api('GET', '/api/accounts');
    document.getElementById('realm-info').textContent = d.release + ' · ' + d.accounts.length + ' account(s)';
    const tbody = document.getElementById('tbl');
    if (!d.accounts.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="color:#484f58">No accounts yet — create one above.</td></tr>'; return;
    }
    tbody.innerHTML = d.accounts.map(a =>
      `<tr>
        <td>${a.id}</td>
        <td>${a.username}</td>
        <td>${a.last_login || '—'}</td>
        <td class="${a.online ? 'online' : 'offline'}">${a.online ? '● Online' : '○ Offline'}</td>
        <td>${a.gmlevel > 0 ? '<span class="gm">GM ' + a.gmlevel + '</span>' : '0'}</td>
        <td><div class="acts">
          <button class="btn btn-secondary btn-sm" onclick="open_pw('${a.username}')">Password</button>
          <button class="btn btn-secondary btn-sm" onclick="open_gm('${a.username}', ${a.gmlevel})">GM Level</button>
        </div></td>
      </tr>`).join('');
  } catch(e) {
    document.getElementById('tbl').innerHTML =
      '<tr><td colspan="6" style="color:#f85149">' + e.message + '</td></tr>';
  }
}

async function createAccount() {
  const user = document.getElementById('new-user').value;
  const pass = document.getElementById('new-pass').value;
  try {
    await api('POST', '/api/accounts', {username: user, password: pass});
    msg('create-msg', 'Account created: ' + user.trim().toUpperCase(), true);
    document.getElementById('new-user').value = '';
    document.getElementById('new-pass').value = '';
    loadAccounts();
  } catch(e) { msg('create-msg', e.message, false); }
}

function open_pw(user) {
  document.getElementById('pw-user').value = user;
  document.getElementById('pw-new').value = '';
  document.getElementById('pw-msg').style.display = 'none';
  document.getElementById('pw-modal').classList.add('open');
  setTimeout(() => document.getElementById('pw-new').focus(), 50);
}

async function submit_password() {
  const user = document.getElementById('pw-user').value;
  const pass = document.getElementById('pw-new').value;
  try {
    await api('POST', '/api/accounts/' + user + '/password', {password: pass});
    msg('pw-msg', 'Password updated.', true);
    setTimeout(() => close_modal('pw-modal'), 1200);
  } catch(e) { msg('pw-msg', e.message, false); }
}

function open_gm(user, current) {
  document.getElementById('gm-user').value = user;
  document.getElementById('gm-label').textContent = user;
  document.getElementById('gm-level').value = current;
  document.getElementById('gm-msg').style.display = 'none';
  document.getElementById('gm-modal').classList.add('open');
}

async function submit_gmlevel() {
  const user = document.getElementById('gm-user').value;
  const level = parseInt(document.getElementById('gm-level').value, 10);
  try {
    await api('POST', '/api/accounts/' + user + '/gmlevel', {level});
    msg('gm-msg', 'GM level set to ' + level + '.', true);
    setTimeout(() => { close_modal('gm-modal'); loadAccounts(); }, 1000);
  } catch(e) { msg('gm-msg', e.message, false); }
}

function close_modal(id) { document.getElementById(id).classList.remove('open'); }
document.querySelectorAll('.modal-bg').forEach(el =>
  el.addEventListener('click', e => { if (e.target === el) close_modal(el.id); }));

loadAccounts();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Dev mode
# ---------------------------------------------------------------------------

def dev_start():
    """Start a temporary MySQL container and return a fake installation state."""
    name = _DEV_PROJECT + "-database"

    existing = _docker_inspect("container", name)
    if existing:
        if existing["State"].get("Running"):
            print(f"Reusing existing dev container '{name}'.")
        else:
            subprocess.run(["docker", "rm", name], capture_output=True)
            existing = None

    if not existing:
        print(f"Starting dev database container '{name}'...")
        subprocess.run([
            "docker", "run", "-d",
            "--name", name,
            "--label", f"{OWNER}={_DEV_ID}",
            "-e", f"MYSQL_ROOT_PASSWORD={_DEV_PASSWORD}",
            "-e", "MYSQL_ROOT_HOST=%",
            _DEV_IMAGE,
        ], check=True, capture_output=True)

    _wait_dev_db(name)
    _create_dev_schema(name)
    return {
        "project": _DEV_PROJECT,
        "release_id": "dev",
        "root": "dev-mode",
        "id": _DEV_ID,
        "phase": "ready",
    }


def dev_teardown():
    """Stop and remove the temporary dev database container."""
    name = _DEV_PROJECT + "-database"
    print(f"\nStopping dev container '{name}'...")
    subprocess.run(["docker", "stop", name], capture_output=True)
    subprocess.run(["docker", "rm", name], capture_output=True)
    print("Dev container removed.")


def _wait_dev_db(container_name, timeout=60):
    print("Waiting for database to be ready", end="", flush=True)
    inner = (
        f"export MYSQL_PWD={_DEV_PASSWORD}; "
        "mysqladmin --no-defaults --no-login-paths --user=root ping --silent 2>/dev/null"
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["docker", "exec", container_name, "sh", "-c", inner],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            print(" ready.", flush=True)
            return
        print(".", end="", flush=True)
        time.sleep(2)
    raise ValueError("Database did not become ready within timeout; check docker logs " + container_name)


def _create_dev_schema(container_name):
    inner = (
        f"export MYSQL_PWD={_DEV_PASSWORD}; "
        "mysql --no-defaults --no-login-paths --user=root"
    )
    result = subprocess.run(
        ["docker", "exec", "-i", container_name, "sh", "-c", inner],
        input=_DEV_SCHEMA, text=True, capture_output=True, timeout=30,
    )
    _require(result.returncode == 0,
             "Schema setup failed: " + result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown")


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, state=None, **kwargs):
        self._state = state
        super().__init__(*args, **kwargs)

    def log_message(self, fmt, *args):
        pass  # silence default per-request logging

    def _json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def do_GET(self):
        if self.path in ("/", ""):
            data = _HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/api/accounts":
            try:
                accounts = list_accounts(self._state["project"])
                self._json(200, {"release": self._state["release_id"], "accounts": accounts})
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                self._json(503, {"error": str(exc)})
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self):
        try:
            body = self._read_body()
        except (json.JSONDecodeError, ValueError):
            self._json(400, {"error": "Invalid JSON body"})
            return

        project = self._state["project"]

        if self.path == "/api/accounts":
            try:
                create_account(project, body.get("username", ""), body.get("password", ""))
                self._json(200, {"ok": True})
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except (OSError, subprocess.SubprocessError) as exc:
                self._json(503, {"error": str(exc)})
            return

        m = _ACCOUNT_PATH_RE.fullmatch(self.path)
        if not m:
            self._json(404, {"error": "Not found"})
            return

        username = urllib.parse.unquote(m.group(1)).upper()
        action = m.group(2)

        if action == "password":
            try:
                change_password(project, username, body.get("password", ""))
                self._json(200, {"ok": True})
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except (OSError, subprocess.SubprocessError) as exc:
                self._json(503, {"error": str(exc)})
            return

        if action == "gmlevel":
            level = body.get("level")
            try:
                _require(isinstance(level, int), "level must be an integer 0–3")
                set_gmlevel(project, username, level)
                self._json(200, {"ok": True})
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except (OSError, subprocess.SubprocessError) as exc:
                self._json(503, {"error": str(exc)})
            return

        self._json(404, {"error": "Unknown action"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    _require(sys.version_info >= (3, 11), "Python 3.11 or newer is required")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir",
                    help="Runtime directory of an existing ready G1 installation")
    ap.add_argument("--dev", action="store_true",
                    help="Start a local MySQL container for UI development (no installation needed)")
    ap.add_argument("--port", type=int, default=8080,
                    help="Localhost port to serve on (default: 8080)")
    args = ap.parse_args()

    if not args.dev and not args.dir:
        print("G1 portal: provide --dir for a real installation or --dev for local development",
              file=sys.stderr)
        return 1

    if not (1024 <= args.port <= 65535):
        print("G1 portal: port must be between 1024 and 65535", file=sys.stderr)
        return 1

    if args.dev:
        try:
            state = dev_start()
        except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
            print("G1 portal: " + str(exc), file=sys.stderr)
            return 1
    else:
        try:
            _root, state = owned(args.dir)
        except (ValueError, KeyError, OSError) as exc:
            print("G1 portal: " + str(exc), file=sys.stderr)
            return 1

    def handler_factory(*a, **kw):
        return _Handler(*a, state=state, **kw)

    server = HTTPServer(("127.0.0.1", args.port), handler_factory)
    print(f"CoA Account Manager running at http://localhost:{args.port}")
    if args.dev:
        print("Mode: development (temporary local database)")
    else:
        print(f"Installation: {state['release_id']} at {state['root']}")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if args.dev:
            dev_teardown()
        else:
            print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
