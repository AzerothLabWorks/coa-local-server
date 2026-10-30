#!/usr/bin/env python3
"""Container-side build and one-time empty-database initialization."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path("/g1")
SOURCE = ROOT / "source"
STATE = ROOT / "state"
SCHEMAS = ("acore_auth", "acore_characters", "acore_world", "acore_playerbots")
SAFE_BOT_UPDATES = ("rev_20261004_00_coa_metadata.sql", "rev_20261004_00_coa_rotations.sql")
CHARACTER_SCHEMA_DEPENDENCIES = {
    "modules/mod-worldforged-pickups/data/sql/db-characters/2026_09_16_00_worldforged_loot.sql":
        "42e4fb03efe4de777c72a8b80b5bc31065c6b454610d4c4635bb61290ef82304",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def run(command, **kwargs):
    return subprocess.run([str(value) for value in command], check=True, **kwargs)


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def digest(path, algorithm="sha256"):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def settings():
    state, manifest = load(ROOT / "installation.json"), load(STATE / "release.json")
    require(state["release_manifest_sha256"] == digest(STATE / "release.json"), "Release manifest changed")
    require(os.getuid() == state["uid"] and os.getgid() == state["gid"], "Unexpected container user")
    for patch in manifest["patches"]:
        target = SOURCE if patch["target"] == "core" else SOURCE / "modules/mod-playerbots"
        for relative, record in patch.get("files", {}).items():
            path = target / relative
            require(path.is_file() and not path.is_symlink() and digest(path) == record["sha256"],
                    "Release source changed: " + relative)
    for overlay in manifest["overlays"]:
        for relative, wanted in overlay["files"].items():
            path = SOURCE / overlay["target"] / relative
            require(path.is_file() and not path.is_symlink() and digest(path) == wanted,
                    "Release module changed: " + relative)
    return state, manifest


def verify_mysql_client():
    result = subprocess.run(["/usr/bin/mysql", "--no-defaults", "--no-login-paths", "--help"],
                            text=True, capture_output=True)
    require(result.returncode == 0,
            "Toolchain MySQL client must support --no-login-paths; rebuild the G1 toolchain with its pinned 8.4 client")


def build():
    state, manifest = settings()
    require(state["phase"] == "planned", "Build is only valid for a fresh installation")
    verify_mysql_client()
    modules = [path.name for path in (SOURCE / "modules").iterdir() if path.is_dir() and path.name.startswith("mod-")]
    arguments = ["-G", "Ninja", "-DCMAKE_BUILD_TYPE=RelWithDebInfo", "-DCMAKE_INSTALL_PREFIX=/g1/install",
                 "-DCONF_DIR=/g1/etc", "-DBUILD_TESTING=ON", "-DAPPS_BUILD=all", "-DTOOLS_BUILD=all",
                 "-DSCRIPTS=static", "-DMODULES=static", "-DCMAKE_CXX_COMPILER=clang++", "-DCMAKE_C_COMPILER=clang",
                 "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"]
    arguments += ["-DMODULE_" + name.upper() + "=" + ("static" if name in manifest["modules"] else "disabled")
                  for name in sorted(modules)]
    config = {"build_directory": "/g1/build", "worldserver": "/g1/build/src/server/apps/worldserver",
              "cmake_args": arguments, "dbc_directory": "/g1/data/dbc"}
    save(STATE / "verify-settings.json", config)
    run([sys.executable, "-B", SOURCE / "tools/verify_all.py", "--settings", STATE / "verify-settings.json",
         "--stages", "source,build,unit", "--base", manifest["core"]["revision"],
         "--output", STATE / "verification"], cwd=SOURCE)
    report = load(STATE / "verification/report.json")
    require(report["status"] == "passed", "Source/build/unit verification did not pass")
    compiled = {entry["file"] for entry in load(ROOT / "build/compile_commands.json")}
    for module in manifest["modules"]:
        missing = {str(p) for p in (SOURCE / "modules" / module).rglob("*.cpp")} - compiled
        require(not missing, "Enabled module has uncompiled sources: " + str(sorted(missing)))
    run(["cmake", "--install", ROOT / "build"])


def mysql(query=None, *, schema=None, file=None):
    command = ["/usr/bin/mysql", "--defaults-extra-file=/g1/state/admin.cnf", "--no-login-paths", "--default-character-set=utf8mb4",
               "--batch", "--skip-column-names"]
    if schema:
        require(schema in SCHEMAS, "Unexpected database name")
        command.append(schema)
    if file:
        with file.open("rb") as stream:
            run(command, stdin=stream)
        return ""
    return run(command, input=query, text=True, stdout=subprocess.PIPE).stdout.strip()


def change_config(path, values):
    require(path.is_file() and not path.is_symlink(), "Configuration template is missing: " + str(path))
    text = path.read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines():
        match = re.match(r"^\s*([A-Za-z0-9_.]+)\s*=", line)
        if not match or match[1] not in values:
            lines.append(line)
    for key, value in values.items():
        require(re.fullmatch(r"[A-Za-z0-9_.]+", key) and "\n" not in str(value) and "\r" not in str(value),
                "Invalid configuration setting")
        lines.append(key + " = " + str(value))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)


def runtime_configuration(state, manifest, password):
    for path in sorted((ROOT / "etc").rglob("*.conf.dist")):
        target = path.with_suffix("")
        require(not target.exists(), "Configuration already exists: " + str(target))
        target.write_bytes(path.read_bytes())
        target.chmod(0o600)
    allowed = {"worldserver.conf", "authserver.conf", "modules/coa.conf", "modules/playerbots.conf",
               "modules/destiny_weaver.conf", "modules/LocalGatheringAlerts.conf"}
    for relative, values in manifest["settings"].items():
        require(relative in allowed and isinstance(values, dict), "Unknown configuration section")
        change_config(ROOT / "etc" / relative, values)
    common = {"LogsDir": '"/g1/logs"', "TempDir": '"/g1/tmp"', "SourceDirectory": '"/g1/source"',
              "MySQLExecutable": '"/usr/bin/mysql"', "Updates.EnableDatabases": "0", "Updates.AutoSetup": "0",
              "Updates.AllowRehash": "0", "Updates.CleanDeadRefMaxCount": "0",
              "Updates.AllowedModules": '"' + ",".join(manifest["modules"]) + '"',
              "Appender.Console": "1,4,0", "Logger.root": "3,Console", "BindIP": '"0.0.0.0"'}
    connections = {name + "DatabaseInfo": '"database;3306;g1;' + password + ";" + schema + '"'
                   for name, schema in (("Login", "acore_auth"), ("Character", "acore_characters"),
                                        ("World", "acore_world"), ("Playerbots", "acore_playerbots"))}
    change_config(ROOT / "etc/authserver.conf", {**common, "LoginDatabaseInfo": connections["LoginDatabaseInfo"],
                  "RealmServerPort": "3724", "RealmID": "1"})
    change_config(ROOT / "etc/worldserver.conf", {**common, **connections, "DataDir": '"/g1/data"',
        "WorldServerPort": "8085", "RealmID": "1", "Console.Enable": "1", "Ra.Enable": "0", "SOAP.Enabled": "0",
        "CoAGameplayTest.Enable": "0", "Cluster.Enabled": "0"})
    configured_accounts = int(manifest["settings"].get("modules/playerbots.conf", {}).get("AiPlayerbot.RandomBotAccountCount", 201))
    change_config(ROOT / "etc/modules/playerbots.conf", {"PlayerbotsDatabaseInfo": connections["PlayerbotsDatabaseInfo"],
        "Playerbots.Updates.EnableDatabases": "0", "Playerbots.Updates.CoaSafeProfiles": "1",
        "AiPlayerbot.MinRandomBots": str(state["bots"]), "AiPlayerbot.MaxRandomBots": str(state["bots"]),
        "AiPlayerbot.RandomBotAccountCount": str(max(configured_accounts, (state["bots"] + 7) // 8)),
        "AiPlayerbot.RandomBotAutologin": "1" if state["bots"] else "0"})


def import_bot_updates():
    module = SOURCE / "modules/mod-playerbots/data/sql/playerbots"
    require(mysql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='acore_playerbots';") == "0",
            "Playerbots base import requires a new empty schema")
    for path in sorted((module / "base").glob("*.sql")):
        mysql(file=path, schema="acore_playerbots")
    ledger = {}
    for directory, names, state in ((module / "updates", None, "RELEASED"),
                                    (SOURCE / "data/sql/updates/pending_db_playerbots", SAFE_BOT_UPDATES, "MODULE")):
        paths = [directory / name for name in names] if names else sorted(directory.glob("*.sql"))
        for path in paths:
            require(re.fullmatch(r"[A-Za-z0-9_.-]+\.sql", path.name), "Invalid migration name")
            checksum = digest(path, "sha1")
            require(mysql("SELECT COUNT(*) FROM updates WHERE name='" + path.name + "';", schema="acore_playerbots") == "0",
                    "Unexpected migration identity already exists: " + path.name)
            mysql(file=path, schema="acore_playerbots")
            mysql("INSERT INTO updates(name,hash,state,speed) VALUES ('" + path.name + "','" + checksum + "','" + state + "',0);",
                  schema="acore_playerbots")
            require(mysql("SELECT CONCAT(hash,':',state) FROM updates WHERE name='" + path.name + "';",
                          schema="acore_playerbots") == checksum + ":" + state, "Migration ledger did not match")
            ledger[path.name] = {"sha1": checksum, "state": state}
    return ledger


def import_character_schema():
    """Supply core prepared-statement dependencies without enabling optional gameplay modules."""
    require(mysql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='acore_characters';") == "0",
            "Character base import requires a new empty schema")
    base = sorted((SOURCE / "data/sql/base/db_characters").glob("*.sql"))
    require({"characters.sql", "updates.sql"}.issubset({path.name for path in base}), "Canonical character base is missing")
    # DBUpdater::Populate skips a non-empty schema, so populate the complete canonical base before its dependency.
    for path in base:
        mysql(file=path, schema="acore_characters")
    require(mysql("SELECT COUNT(*) FROM characters;", schema="acore_characters") == "0",
            "Canonical character base unexpectedly contains player data")
    enum = mysql("SELECT COLUMN_TYPE FROM information_schema.columns WHERE table_schema='acore_characters' "
                 "AND table_name='updates' AND column_name='state';")
    require("'MODULE'" in enum.upper(), "Canonical character migration ledger does not support MODULE identities")
    ledger = {}
    for relative, expected in CHARACTER_SCHEMA_DEPENDENCIES.items():
        path = SOURCE / relative
        require(digest(path) == expected, "Canonical character schema dependency changed: " + relative)
        require(mysql("SELECT COUNT(*) FROM updates WHERE name='" + path.name + "';", schema="acore_characters") == "0",
                "Character dependency migration identity already exists")
        mysql(file=path, schema="acore_characters")
        checksum = digest(path, "sha1")
        mysql("INSERT INTO updates(name,hash,state,speed) VALUES ('" + path.name + "','" + checksum + "','MODULE',0);",
              schema="acore_characters")
        require(mysql("SELECT CONCAT(hash,':',state) FROM updates WHERE name='" + path.name + "';",
                      schema="acore_characters") == checksum + ":MODULE", "Character dependency ledger did not match")
        ledger[path.name] = {"source": relative, "sha256": expected, "sha1": checksum, "state": "MODULE"}
    return {"base_files": {path.name: digest(path) for path in base}, "dependencies": ledger}


def grant_runtime_privileges():
    for schema in SCHEMAS:
        mysql("GRANT SELECT,INSERT,UPDATE,DELETE,EXECUTE,CREATE TEMPORARY TABLES ON " + schema + ".* TO 'g1'@'%';")
    # Canonical daily guild reset and GM ticket reset use TRUNCATE, which MySQL authorizes with DROP.
    for table in ("guild_member_withdraw", "gm_ticket"):
        mysql("GRANT DROP ON acore_characters." + table + " TO 'g1'@'%';")


def bootstrap():
    state, manifest = settings()
    require(state["phase"] == "bootstrap-started", "Bootstrap is only valid for a new installation")
    require(not (STATE / "bootstrap-attempt.json").exists(), "An earlier bootstrap was attempted; never replay it")
    save(STATE / "bootstrap-attempt.json", {"installation": state["id"], "release": state["release_id"]})
    require(mysql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema NOT IN "
                  "('mysql','information_schema','performance_schema','sys');") == "0",
            "Bootstrap refuses any database containing non-system tables")
    for schema in SCHEMAS:
        mysql("CREATE DATABASE IF NOT EXISTS " + schema + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    run([sys.executable, "-B", SOURCE / "apps/coa-world/world_data.py", "verify"], cwd=SOURCE)
    run([sys.executable, "-B", SOURCE / "apps/coa-world/world_data.py", "bootstrap", "--defaults-file",
         STATE / "admin.cnf", "--database", "acore_world"], cwd=SOURCE)
    character_schema = import_character_schema()
    admin = (STATE / "admin.cnf").read_text(encoding="utf-8")
    match = re.search(r"^password=([0-9a-f]{64})$", admin, re.M)
    require(match, "Invalid generated administrator credential")
    config = ["SourceDirectory = \"/g1/source\"", "MySQLExecutable = \"/usr/bin/mysql\"", "TempDir = \"/g1/tmp\"",
              "LogsDir = \"/g1/logs\"", "Updates.EnableDatabases = 7", "Updates.AutoSetup = 1", "Updates.Redundancy = 1",
              "Updates.ArchivedRedundancy = 0", "Updates.AllowRehash = 0", "Updates.CleanDeadRefMaxCount = 0",
              'Updates.AllowedModules = "' + ",".join(manifest["modules"]) + '"', "Appender.Console = 1,4,0", "Logger.root = 3,Console"]
    for name, schema in (("Login", "acore_auth"), ("Character", "acore_characters"), ("World", "acore_world")):
        config.extend([name + 'DatabaseInfo = "database;3306;root;' + match[1] + ";" + schema + '"',
                       name + "Database.WorkerThreads = 1", name + "Database.SynchThreads = 1"])
    config_path = STATE / "dbimport.conf"
    with config_path.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(config) + "\n")
    run([ROOT / "build/src/tools/dbimport", "-c", config_path], cwd=SOURCE)
    ledger = import_bot_updates()
    require(mysql("SELECT COUNT(*) FROM acore_auth.account;") == "0" and
            mysql("SELECT COUNT(*) FROM acore_characters.characters;") == "0", "Fresh bootstrap unexpectedly contains player accounts")
    password = (STATE / "runtime-password").read_text(encoding="utf-8").strip()
    require(re.fullmatch(r"[0-9a-f]{64}", password), "Invalid generated runtime credential")
    mysql("CREATE USER 'g1'@'%' IDENTIFIED BY '" + password + "';")
    grant_runtime_privileges()
    mysql("INSERT INTO acore_auth.realmlist (id,name,address,localAddress,localSubnetMask,port,icon,flag,timezone,"
          "allowedSecurityLevel,population,gamebuild) VALUES (1,'AzerothLabWorks G1','127.0.0.1','127.0.0.1',"
          "'255.255.255.0'," + str(state["ports"]["worldserver"]) + ",0,0,1,0,0,12340) ON DUPLICATE KEY UPDATE "
          "name=VALUES(name),address=VALUES(address),localAddress=VALUES(localAddress),localSubnetMask=VALUES(localSubnetMask),"
          "port=VALUES(port),flag=0,gamebuild=VALUES(gamebuild);")
    runtime_configuration(state, manifest, password)
    save(STATE / "bootstrap.json", {"status": "passed", "installation": state["id"], "player_accounts": 0,
                                  "characters": 0, "character_schema": character_schema,
                                  "playerbots_migrations": ledger, "runtime_updaters_enabled": False})


if __name__ == "__main__":
    os.umask(0o077)
    require(len(sys.argv) == 2 and sys.argv[1] in ("build", "bootstrap"), "Expected build or bootstrap")
    globals()[sys.argv[1]]()
