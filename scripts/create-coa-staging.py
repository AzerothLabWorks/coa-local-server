#!/usr/bin/env python3
"""Capture a private recovery checkpoint and restore an isolated baseline realm."""

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time


SCHEMAS = ("acore_auth", "acore_characters", "acore_world", "acore_playerbots")
REPO = Path(__file__).resolve().parent.parent
PORTS = {"DB": 33307, "AUTH": 33725, "WORLD": 38086, "SOAP": 37879}


def run(command, **kwargs):
    result = subprocess.run(command, check=False, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed (exit {result.returncode}); private checkpoint retained")
    return result


def output(command):
    return run(command, capture_output=True, text=True).stdout


def write_private(path, text):
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)


def write_json(path, value):
    write_private(path, json.dumps(value, indent=2) + "\n")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sql(container, query):
    return output([
        "docker", "exec", container, "sh", "-c",
        'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql --user=root --batch '
        '--skip-column-names --execute="$1"', "mysql-query", query,
    ])


def inspect(container):
    return json.loads(output(["docker", "inspect", container]))[0]


def environment(info):
    return dict(item.split("=", 1) for item in info["Config"]["Env"])


def env_text(values, raw=False):
    lines = []
    for key, value in sorted(values.items()):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or "\n" in value or "\r" in value:
            raise ValueError("Unsupported environment entry")
        rendered = value if raw else json.dumps(value.replace("$", "$$"))
        lines.append(f"{key}={rendered}")
    return "\n".join(lines) + "\n"


def validate_destination(live, staging, project):
    if not live.is_absolute() or not staging.is_absolute():
        raise ValueError("Runtime paths must be absolute")
    if staging == live or staging.is_relative_to(live) or live.is_relative_to(staging):
        raise ValueError("Staging and live runtime paths must not overlap")
    if staging.exists():
        raise ValueError("Staging destination already exists; it will not be overwritten")
    if not re.fullmatch(r"coa-staging-[a-z0-9][a-z0-9-]*", project):
        raise ValueError("Use a distinct coa-staging-* project name")


def source_path(live):
    for line in (live / ".env").read_text().splitlines():
        if line.startswith("COA_SOURCE_DIR="):
            path = Path(line.split("=", 1)[1].strip().strip('"\''))
            if path.is_absolute() and path.is_dir():
                return path.resolve()
    raise ValueError("Active source path missing from live .env")


def database_signature(container):
    schemas = ",".join(f"'{name}'" for name in SCHEMAS)
    tables = sql(container, "SELECT TABLE_SCHEMA,TABLE_NAME,ENGINE,TABLE_COLLATION "
                 f"FROM information_schema.TABLES WHERE TABLE_SCHEMA IN ({schemas}) "
                 "AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_SCHEMA,TABLE_NAME;")
    entries = [line.split("\t") for line in tables.splitlines()]
    if any(len(entry) != 4 or not re.fullmatch(r"[A-Za-z0-9_]+", entry[1]) for entry in entries):
        raise RuntimeError("Invalid table metadata returned")
    if set(entry[0] for entry in entries) != set(SCHEMAS):
        raise RuntimeError("All four expected schemas must contain tables")
    columns = sql(container, "SELECT TABLE_SCHEMA,TABLE_NAME,COLUMN_NAME,ORDINAL_POSITION,COLUMN_TYPE,"
                  "IS_NULLABLE,IFNULL(COLUMN_DEFAULT,'<NULL>'),EXTRA,IFNULL(COLLATION_NAME,'<NULL>') "
                  f"FROM information_schema.COLUMNS WHERE TABLE_SCHEMA IN ({schemas}) "
                  "ORDER BY TABLE_SCHEMA,TABLE_NAME,ORDINAL_POSITION;")
    names = [f"`{entry[0]}`.`{entry[1]}`" for entry in entries]
    checksums = sql(container, "CHECKSUM TABLE " + ",".join(names) + " EXTENDED;")
    if any(line.endswith("\tNULL") for line in checksums.splitlines()):
        raise RuntimeError("A table checksum is unavailable; restore equality is not established")
    counts = sql(container, " UNION ALL ".join(
        f"SELECT '{entry[0]}.{entry[1]}',COUNT(*) FROM {name}"
        for entry, name in zip(entries, names)) + ";")
    for label, results in (("checksums", checksums), ("counts", counts)):
        rows = [row.split("\t") for row in results.splitlines()]
        if len(rows) != len(entries) or any(len(row) != 2 or not row[1].isdigit() for row in rows):
            raise RuntimeError(f"Incomplete {label} output")
    if not columns.strip():
        raise RuntimeError("Column metadata is missing")
    indexes = sql(container, "SELECT TABLE_SCHEMA,TABLE_NAME,INDEX_NAME,NON_UNIQUE,SEQ_IN_INDEX,"
                  "IFNULL(COLUMN_NAME,'<NULL>'),IFNULL(SUB_PART,0),INDEX_TYPE,IS_VISIBLE "
                  f"FROM information_schema.STATISTICS WHERE TABLE_SCHEMA IN ({schemas}) "
                  "ORDER BY TABLE_SCHEMA,TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX;")
    objects = sql(container, "SELECT 'routine',ROUTINE_SCHEMA,ROUTINE_NAME FROM information_schema.ROUTINES "
                  f"WHERE ROUTINE_SCHEMA IN ({schemas}) UNION ALL "
                  "SELECT 'trigger',TRIGGER_SCHEMA,TRIGGER_NAME FROM information_schema.TRIGGERS "
                  f"WHERE TRIGGER_SCHEMA IN ({schemas}) UNION ALL "
                  "SELECT 'event',EVENT_SCHEMA,EVENT_NAME FROM information_schema.EVENTS "
                  f"WHERE EVENT_SCHEMA IN ({schemas}) UNION ALL "
                  "SELECT 'view',TABLE_SCHEMA,TABLE_NAME FROM information_schema.VIEWS "
                  f"WHERE TABLE_SCHEMA IN ({schemas});")
    if objects.strip():
        raise RuntimeError("Additional routines/triggers/events/views require a dedicated restore check")
    return {"tables": tables, "columns": columns, "indexes": indexes,
            "checksums": checksums, "counts": counts, "objects": objects}


def dump_database(container, path):
    command = ["docker", "exec", container, "sh", "-c",
               'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysqldump --user=root '
               '--lock-all-tables --quick --routines --events --triggers --hex-blob '
               '--set-gtid-purged=OFF --no-tablespaces --column-statistics=0 --databases '
               + " ".join(SCHEMAS)]
    with (path.parent / "dump.stderr").open("wb") as errors, path.open("wb") as target:
        run(command, stdout=target, stderr=errors)
    path.chmod(0o600)


def resume_live(services, checkpoint):
    try:
        run(["docker", "start", services["authserver"]["Id"], services["worldserver"]["Id"]],
            stdout=subprocess.DEVNULL)
        time.sleep(1)
        if any(not inspect(services[role]["Id"])["State"]["Running"]
               for role in ("authserver", "worldserver")):
            raise RuntimeError("A live service stopped immediately after restart")
    except (RuntimeError, OSError) as error:
        names = " ".join(services[role]["Name"].lstrip("/") for role in ("authserver", "worldserver"))
        raise RuntimeError(f"Live recovery needs attention: docker start {names}; checkpoint {checkpoint}") from error


def stream_archive(command, destination):
    with destination.open("wb") as target:
        run(command, stdout=target)
    destination.chmod(0o600)


def compose(staging, *arguments):
    return ["docker", "compose", "--project-directory", str(staging), "--env-file",
            str(staging / ".env"), "-f", str(staging / "compose.yaml"), *arguments]


def capture_database_checkpoint(services, checkpoint, metadata):
    print("Pausing live auth/world for a consistent four-schema checkpoint...", flush=True)
    pause_started = time.monotonic()
    try:
        run(["docker", "stop", "--time", "120", services["authserver"]["Id"], services["worldserver"]["Id"]],
            stdout=subprocess.DEVNULL)
        stopped = {role: inspect(services[role]["Id"])["State"] for role in ("authserver", "worldserver")}
        if any(state["Running"] or state["OOMKilled"] or state["ExitCode"] == 137 for state in stopped.values()):
            raise RuntimeError("A live writer did not stop cleanly")
        metadata["paused_states"] = stopped
        metadata["database_signature"] = database_signature(services["database"]["Id"])
        dump_database(services["database"]["Id"], checkpoint / "databases.sql")
        metadata["database_dump_sha256"] = digest(checkpoint / "databases.sql")
        run(["docker", "cp", services["worldserver"]["Id"] + ":/azerothcore/env/dist/etc", str(checkpoint / "etc")])
        metadata["status"] = "database-captured"
        write_json(checkpoint / "checkpoint.json", metadata)
    finally:
        resume_live(services, checkpoint)
        print(f"Live auth/world resumed after {time.monotonic() - pause_started:.0f} seconds.", flush=True)


def seal_checkpoint(checkpoint, metadata):
    """Persist preserved-file evidence before any staging restore/start can fail."""
    if digest(checkpoint / "databases.sql") != metadata["database_dump_sha256"]:
        raise RuntimeError("Saved database dump no longer matches the checkpoint")
    archives = ("active-source.tar.gz", "installer-source.tar.gz", "runtime-images.tar")
    hashes = {name: digest(checkpoint / name) for name in archives}
    if "archive_sha256" in metadata and hashes != metadata["archive_sha256"]:
        raise RuntimeError("A preserved recovery archive changed")
    data_hashes = {str(path.relative_to(checkpoint / "data")): digest(path)
                   for path in sorted((checkpoint / "data").rglob("*")) if path.is_file()}
    if not data_hashes:
        raise RuntimeError("Recovery server data is missing")
    if "data_hashes" in metadata and data_hashes != metadata["data_hashes"]:
        raise RuntimeError("Preserved server data changed")
    metadata["archive_sha256"] = hashes
    metadata["data_hashes"] = data_hashes
    metadata["preserved_files_verified_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    write_json(checkpoint / "checkpoint.json", metadata)


def validate_stage_configuration(configuration, staging, checkpoint, metadata):
    """Refuse changed image pins, live database routes, or shared mutable storage."""
    project = metadata["project"]
    services = configuration.get("services", {})
    if configuration.get("name") != project or set(services) != {"database", "authserver", "worldserver"}:
        raise RuntimeError("Staging Compose project/service identity changed")
    password = services["database"]["environment"]["MYSQL_ROOT_PASSWORD"]
    if not password or password == environment(metadata["services"]["database"])["MYSQL_ROOT_PASSWORD"]:
        raise RuntimeError("Staging must use a separate database credential")
    database_keys = {"AC_LOGIN_DATABASE_INFO": "acore_auth", "AC_WORLD_DATABASE_INFO": "acore_world",
                     "AC_CHARACTER_DATABASE_INFO": "acore_characters", "AC_PLAYERBOTS_DATABASE_INFO": "acore_playerbots"}
    for role, service in services.items():
        if service["image"] != metadata["services"][role]["Image"]:
            raise RuntimeError("A staging image differs from the checkpoint")
        if role == "database":
            if service.get("ports") or set(service.get("networks", {})) != {"default"}:
                raise RuntimeError("Staging MySQL must have no public ingress")
            if service["volumes"] != [{"type": "volume", "source": "staging-database", "target": "/var/lib/mysql", "volume": {}}]:
                raise RuntimeError("Unexpected staging database storage")
            continue
        values = service["environment"]
        required = database_keys if role == "worldserver" else {"AC_LOGIN_DATABASE_INFO": "acore_auth"}
        for key, schema in required.items():
            if values.get(key) != f"database;3306;root;{password};{schema}":
                raise RuntimeError("A staging database connection is not isolated")
        for key in ("AC_UPDATES_ENABLE_DATABASES", "AC_UPDATES_AUTO_SETUP"):
            if str(values.get(key)) != "0":
                raise RuntimeError("Baseline database updates must remain disabled")
        if role == "worldserver" and any(str(values.get(key)) != "0" for key in
                                         ("AC_PLAYERBOTS_UPDATES_ENABLE_DATABASES", "AC_SOAP_ENABLED", "AC_RA_ENABLE")):
            raise RuntimeError("Unexpected staging updater/admin service configuration")
        expected = {"/azerothcore/env/dist/etc": (str(staging / "etc"), False),
                    "/azerothcore/env/dist/logs": (str(staging / "logs"), False)}
        if role == "worldserver":
            expected["/azerothcore/env/dist/data"] = (str(checkpoint / "data"), True)
        mounts = {mount["target"]: (mount["source"], bool(mount.get("read_only"))) for mount in service["volumes"]}
        if mounts != expected or any(mount["type"] != "bind" for mount in service["volumes"]):
            raise RuntimeError("Staging file mounts differ from the private checkpoint/runtime")
        if set(service["networks"]) != {"default", "staging-ingress"}:
            raise RuntimeError("Unexpected staging game-service networks")
        expected_ports = {(3724, str(PORTS["AUTH"]))} if role == "authserver" else {
            (8085, str(PORTS["WORLD"])), (7878, str(PORTS["SOAP"]))}
        ports = service.get("ports", [])
        if {(port["target"], str(port["published"])) for port in ports} != expected_ports or any(
                port.get("host_ip") != "127.0.0.1" for port in ports):
            raise RuntimeError("Staging game ports must use their separate loopback bindings")
    if configuration["volumes"]["staging-database"]["name"] != project + "-database":
        raise RuntimeError("Staging volume name changed")
    networks = configuration["networks"]
    if (set(networks) != {"default", "staging-ingress"} or
            networks["default"].get("internal") is not True or
            networks["default"]["name"] != project + "-network" or
            networks["staging-ingress"]["name"] != project + "-ingress"):
        raise RuntimeError("Staging network identity changed")


def verify_and_start(staging, checkpoint, metadata):
    configuration = json.loads(output(compose(staging, "config", "--format", "json")))
    validate_stage_configuration(configuration, staging, checkpoint, metadata)
    staged_db = output(compose(staging, "ps", "-q", "database")).strip()
    if not staged_db or len(staged_db.splitlines()) != 1:
        raise RuntimeError("Expected exactly one isolated staging database")
    db_info = inspect(staged_db)
    if db_info["Image"] != metadata["services"]["database"]["Image"]:
        raise RuntimeError("Staging MySQL must use the checkpoint image")
    project = metadata["project"]
    if db_info["Config"].get("Labels", {}).get("com.docker.compose.project") != project:
        raise RuntimeError("Database does not belong to the isolated staging project")
    volumes = [mount["Name"] for mount in db_info["Mounts"] if mount["Type"] == "volume"]
    if volumes != [project + "-database"]:
        raise RuntimeError("Staging MySQL storage isolation failed")
    if list(db_info["NetworkSettings"]["Networks"]) != [project + "-network"]:
        raise RuntimeError("Staging MySQL must remain on its private backend network")
    for role in ("authserver", "worldserver"):
        if output(compose(staging, "ps", "-a", "-q", role)).strip():
            raise RuntimeError("Staging game services already exist; do not rerun initial restore verification")
    print("Comparing restored schema, row counts and every table checksum...", flush=True)
    restored = database_signature(staged_db)
    failures = [key for key in restored if restored[key] != metadata["database_signature"][key]]
    if failures:
        write_json(checkpoint / "restore-mismatch.json", restored)
        if failures != ["checksums"]:
            raise RuntimeError("Restore comparison failed: " + ", ".join(failures))
        spec = importlib.util.spec_from_file_location("restore_proof", REPO / "scripts/staging-restore-proof.py")
        proof = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(proof)
        metadata["restore_proof"] = proof.verify_restore(
            staged_db, checkpoint, metadata["database_signature"], restored)
    else:
        metadata["restore_proof"] = {"method": "all-table-checksums", "table_count": len(restored["counts"].splitlines())}
    metadata["restore_verified"] = True
    write_json(checkpoint / "checkpoint.json", metadata)
    if sql(staged_db, "SELECT COUNT(*) FROM acore_auth.realmlist;").strip() != "1":
        raise RuntimeError("Expected a single staging realm; extra copied realm routes require review")
    query = "UPDATE acore_auth.realmlist SET name='COA G1 STAGING',address='127.0.0.1'," \
            "localAddress='127.0.0.1',localSubnetMask='255.255.255.0',port=38086,flag=0,gamebuild=12340 WHERE id=1;"
    sql(staged_db, query)
    route = sql(staged_db, "SELECT name,address,localAddress,port,flag FROM acore_auth.realmlist WHERE id=1;").strip()
    if route != "COA G1 STAGING\t127.0.0.1\t127.0.0.1\t38086\t0":
        raise RuntimeError("Staging realm route guard failed")
    metadata["staging_realm_route"] = route
    metadata["status"] = "restore-verified-starting"
    write_json(checkpoint / "checkpoint.json", metadata)
    write_private(staging / "checkpoint-path", str(checkpoint) + "\n")
    print("Restore verified. Starting the isolated baseline realm...", flush=True)
    run(compose(staging, "up", "-d", "--no-build", "--pull", "never", "authserver", "worldserver"))
    metadata["status"] = "baseline-restored"
    write_json(checkpoint / "checkpoint.json", metadata)
    print(f"Checkpoint: {checkpoint}\nStaging: {staging}\nAuth endpoint: 127.0.0.1:33725", flush=True)
    print("Startup/log and in-game checks are still required; no upstream upgrade has been applied.", flush=True)


def resume_checkpoint(args):
    """Finish a restored checkpoint without pausing or modifying live again."""
    live, staging = Path(args.live_dir).resolve(), Path(args.dir).resolve()
    checkpoint = Path(args.resume_checkpoint).resolve()
    if staging == live or staging.is_relative_to(live) or live.is_relative_to(staging):
        raise ValueError("Staging and live runtime paths must not overlap")
    if checkpoint.parent != (live / "state/backups").resolve() or not checkpoint.name.startswith("g1-baseline-"):
        raise ValueError("Resume requires an existing G1 checkpoint inside the named live runtime")
    metadata = json.loads((checkpoint / "checkpoint.json").read_text())
    if (metadata["live_runtime"], metadata["staging_runtime"], metadata["project"]) != (str(live), str(staging), args.project):
        raise ValueError("Checkpoint identity does not match the requested staging runtime")
    if metadata["status"] not in ("database-captured", "recovery-preserved"):
        raise ValueError("Checkpoint is not awaiting initial restore verification")
    seal_checkpoint(checkpoint, metadata)
    # Template contains no secrets; the private environment remains unchanged.
    shutil.copy2(REPO / "compose.staging.yaml", staging / "compose.yaml")
    run(compose(staging, "config", "--quiet"))
    verify_and_start(staging, checkpoint, metadata)


def main(args):
    os.umask(0o077)
    if args.resume_checkpoint:
        resume_checkpoint(args)
        return
    live = Path(args.live_dir).resolve()
    staging = Path(args.dir).resolve()
    validate_destination(live, staging, args.project)
    source = source_path(live)
    services = {}
    for role in ("database", "authserver", "worldserver"):
        ids = output(["docker", "compose", "--project-directory", str(live), "--env-file",
                      str(live / ".env"), "-f", str(live / "compose.yaml"), "ps", "-q", role]).strip()
        if len(ids.splitlines()) != 1 or not ids:
            raise RuntimeError(f"Expected exactly one running live {role}")
        services[role] = inspect(ids)
        if not services[role]["State"]["Running"]:
            raise RuntimeError(f"Live {role} must be running for this checkpoint workflow")
    db = services["database"]["Id"]
    for name in args.require_offline:
        if not re.fullmatch(r"[A-Za-z]+", name):
            raise ValueError("Character names must contain letters only")
        if sql(db, f"SELECT COUNT(*) FROM acore_characters.characters WHERE name='{name}' AND online=1;").strip() != "0":
            raise RuntimeError(f"{name} is still online; checkpoint not started")
    for suffix in ("database", "network", "ingress"):
        resource = "volume" if suffix == "database" else "network"
        if subprocess.run(["docker", resource, "inspect", f"{args.project}-{suffix}"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            raise RuntimeError("Staging Docker resource already exists; not overwriting it")
    for port in PORTS.values():
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    mounts = services["worldserver"]["Mounts"]
    data_mount = next(item for item in mounts if item["Destination"] == "/azerothcore/env/dist/data")
    if data_mount["RW"] or not Path(data_mount["Source"]).is_dir():
        raise RuntimeError("Expected read-only existing live server data")
    backup_root = (live / "state" / "backups").resolve()
    if not backup_root.is_relative_to(live):
        raise ValueError("Backup destination escapes the live runtime")
    backup_root.mkdir(parents=True, exist_ok=True)
    checkpoint = Path(tempfile.mkdtemp(prefix="g1-baseline-" + time.strftime("%Y%m%d-"), dir=backup_root))
    staging.mkdir(mode=0o700)
    metadata = {"status": "capturing", "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "live_runtime": str(live), "staging_runtime": str(staging), "project": args.project,
                "services": services, "source": str(source)}
    write_json(checkpoint / "checkpoint.json", metadata)
    shutil.copy2(live / ".env", checkpoint / "live.env")
    shutil.copy2(live / "compose.yaml", checkpoint / "live-compose.yaml")
    capture_database_checkpoint(services, checkpoint, metadata)
    print("Copying frozen server data and preserving source/configuration/images...", flush=True)
    shutil.copytree(data_mount["Source"], checkpoint / "data")
    source_archive = checkpoint / "active-source.tar.gz"
    stream_archive(["tar", "-czf", "-", "-C", str(source), "."], source_archive)
    stream_archive(["tar", "--exclude=./.runtime", "--exclude=./patches", "-czf", "-",
                    "-C", str(REPO), "."], checkpoint / "installer-source.tar.gz")
    images = list(dict.fromkeys(info["Image"] for info in services.values()))
    stream_archive(["docker", "image", "save", *images], checkpoint / "runtime-images.tar")
    metadata["source_revision"] = output(["git", "-C", str(source), "rev-parse", "HEAD"]).strip()
    metadata["module_revision"] = output(["git", "-C", str(source / "modules/mod-playerbots"), "rev-parse", "HEAD"]).strip()
    metadata["status"] = "recovery-preserved"
    seal_checkpoint(checkpoint, metadata)
    shutil.copytree(checkpoint / "etc", staging / "etc")
    (staging / "logs").mkdir(mode=0o700)
    shutil.copy2(REPO / "compose.staging.yaml", staging / "compose.yaml")
    values = {"COMPOSE_PROJECT_NAME": args.project, "COA_STAGING_DB_PASSWORD": secrets.token_hex(24),
              "COA_STAGING_DATA_DIR": str(checkpoint / "data")}
    for role, key in (("database", "DATABASE"), ("authserver", "AUTH"), ("worldserver", "WORLD")):
        values[f"COA_STAGING_{key}_IMAGE"] = services[role]["Image"]
    values.update({f"COA_STAGING_{key}_PORT": str(port) for key, port in PORTS.items()})
    write_private(staging / ".env", env_text(values))
    for role in ("authserver", "worldserver"):
        inherited = {key: value for key, value in environment(services[role]).items()
                     if not key.endswith("DATABASE_INFO")}
        write_private(staging / f"{role}.env", env_text(inherited, raw=True))
    run(compose(staging, "config", "--quiet"))
    print("Starting isolated MySQL and restoring the checkpoint...", flush=True)
    run(compose(staging, "up", "-d", "--no-build", "--pull", "never", "database"))
    staged_db = output(compose(staging, "ps", "-q", "database")).strip()
    for _ in range(90):
        state = inspect(staged_db)["State"]
        if state.get("Health", {}).get("Status") == "healthy":
            break
        if not state["Running"]:
            raise RuntimeError("Staging MySQL stopped during initialization")
        time.sleep(2)
    else:
        raise RuntimeError("Staging MySQL did not become healthy")
    command = ["docker", "exec", "-i", staged_db, "sh", "-c",
               'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql --user=root']
    with (checkpoint / "databases.sql").open("rb") as dump, (checkpoint / "restore.stderr").open("wb") as errors:
        run(command, stdin=dump, stdout=subprocess.DEVNULL, stderr=errors)
    verify_and_start(staging, checkpoint, metadata)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-dir", required=True)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--project", default="coa-staging-g1")
    parser.add_argument("--require-offline", action="append")
    parser.add_argument("--resume-checkpoint", help="Verify an already restored private checkpoint without pausing live again")
    parser.add_argument("--pause-live", action="store_true", help="Acknowledge a brief live auth/world stop for the backup")
    arguments = parser.parse_args()
    if not arguments.resume_checkpoint and (not arguments.pause_live or not arguments.require_offline):
        parser.error("--pause-live is required after coordinating player logout")
    try:
        main(arguments)
    except (RuntimeError, ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
