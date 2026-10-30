#!/usr/bin/env python3
"""Install and manage a pinned G1 release on Linux or WSL2."""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid


REPOSITORY = Path(__file__).resolve().parents[1]
OWNER = "org.azerothlabworks.g1.installation"
SCHEMAS = ("acore_auth", "acore_characters", "acore_world", "acore_playerbots")
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(command, *, capture=False, **kwargs):
    return subprocess.run([str(value) for value in command], check=True,
                          text=True, stdout=subprocess.PIPE if capture else None, **kwargs)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value, *, replace=False):
    path = Path(path)
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if replace:
        temporary = path.with_name(path.name + ".new-" + uuid.uuid4().hex)
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(text)
        temporary.replace(path)
    else:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(text)
    path.chmod(0o600)


def ordinary(path, *, directory=False):
    path = Path(path).absolute()
    for component in (path, *path.parents):
        require(not component.is_symlink(), "Symbolic links are not accepted: " + str(path))
    require(path.is_dir() if directory else path.is_file(), "Missing ordinary path: " + str(path))
    require(not any(c in str(path) for c in ("\n", "\r", ",", '"')), "Unsupported path characters")
    return path.resolve()


def child(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative,
            "Expected a portable relative path")
    parts = Path(relative).parts
    require(not Path(relative).is_absolute() and not any(p in ("..", ".git") for p in parts),
            "Path escapes the release: " + relative)
    result = Path(root) / relative
    require(result.resolve().is_relative_to(Path(root).resolve()), "Path escaped its root")
    return result


def inventory(root):
    root = ordinary(root, directory=True)
    result = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "Linked artifact rejected: " + str(path))
        if path.is_file():
            result[path.relative_to(root).as_posix()] = digest(path)
    return result


def release(path, repository=REPOSITORY):
    path = ordinary(path)
    data = load(path)
    require(data.get("schema_version") == 1, "Unsupported release manifest version")
    require(re.fullmatch(r"g1-[a-z0-9-]+", data.get("release_id", "")), "Invalid release name")
    for name in ("core", "playerbots"):
        pin = data[name]
        require(COMMIT.fullmatch(pin["revision"]), "An exact public commit is required: " + name)
        require(re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?",
                             pin["repository"]), "Use a public GitHub source URL")
    require(set(data["modules"]) == {"mod-destiny-weaver", "mod-local-profession-tools", "mod-playerbots"},
            "Unexpected module set for this G1 release")
    for patch in data["patches"]:
        require(patch["target"] in ("core", "playerbots") and SHA.fullmatch(patch["sha256"]),
                "Invalid patch declaration")
        require(digest(ordinary(child(repository, patch["path"]))) == patch["sha256"],
                "Release patch checksum mismatch: " + patch["path"])
    for overlay in data["overlays"]:
        child(Path("/source"), overlay["target"])
        require(inventory(child(repository, overlay["source"])) == overlay["files"],
                "Release overlay differs: " + overlay["source"])
    require(data["data"]["dbc_files"] and all(SHA.fullmatch(v) for v in data["data"]["dbc_files"].values()),
            "Release has no valid DBC fingerprints")
    require(re.fullmatch(r"mysql(?::[A-Za-z0-9_.-]+)?@sha256:[0-9a-f]{64}", data["images"]["mysql"]),
            "MySQL image must be digest-pinned")
    return data


def validate_data(data, base, dbc, terrain):
    paths = {"base": ordinary(base, directory=True), "dbc": ordinary(dbc, directory=True),
             "terrain": ordinary(terrain, directory=True)}
    for name in data["data"]["terrain_required"]:
        require(name in ("maps", "vmaps", "mmaps"), "Unknown terrain component")
        directory = ordinary(paths["terrain"] / name, directory=True)
        require(any(directory.iterdir()), "Empty terrain directory: " + str(directory))
    for relative, wanted in data["data"]["dbc_files"].items():
        path = ordinary(child(paths["dbc"], relative))
        require(digest(path) == wanted, "DBC version mismatch: " + relative)
    for relative, wanted in data["data"].get("terrain_files", {}).items():
        require(digest(ordinary(child(paths["terrain"], relative))) == wanted,
                "Terrain version mismatch: " + relative)
    return {key: str(value) for key, value in paths.items()}


def project_name(root, requested=None):
    value = requested or "coa-g1-" + hashlib.sha256(str(root).encode()).hexdigest()[:12]
    require(re.fullmatch(r"coa-g1-[a-z0-9][a-z0-9-]{2,43}", value),
            "Project must start coa-g1- and contain only lowercase letters, digits and hyphens")
    return value


def ports_available(ports):
    require(len(set(ports)) == len(ports) and all(1024 <= p <= 65535 for p in ports), "Invalid or duplicate ports")
    sockets = []
    try:
        for port in ports:
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sockets.append(listener)
            listener.bind(("127.0.0.1", port))
    except OSError as error:
        raise RuntimeError("A requested loopback port is already in use") from error
    finally:
        for listener in sockets:
            listener.close()


def docker_inspect(kind, name):
    result = subprocess.run(["docker", kind, "inspect", name], text=True, capture_output=True)
    if result.returncode:
        require("no such" in result.stderr.lower() or "not found" in result.stderr.lower(), "Docker inspection failed")
        return None
    return json.loads(result.stdout)[0]


def resource_names(project):
    return {"volume": [project + "-database"], "network": [project + "-network"],
            "container": [project + "-" + role for role in ("database", "authserver", "worldserver")]}


def absent_resources(project):
    for kind, names in resource_names(project).items():
        for name in names:
            require(docker_inspect(kind, name) is None, "Existing Docker resource prevents installation: " + name)


def validate_network_subnet(value, occupied):
    try:
        subnet = ipaddress.ip_network(value, strict=True)
    except ValueError as error:
        raise RuntimeError("Network subnet must be an aligned private IPv4 /24") from error
    private = [ipaddress.ip_network(item) for item in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
    require(subnet.version == 4 and subnet.prefixlen == 24 and any(subnet.subnet_of(item) for item in private),
            "Network subnet must be an aligned RFC1918 private IPv4 /24")
    for name, value in occupied:
        if value in (None, "", "default"):
            continue
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError as error:
            raise RuntimeError("Cannot validate an existing network route: " + str(value)) from error
        if network.version == 4 and subnet.overlaps(network):
            raise RuntimeError("Requested subnet overlaps " + name + ": " + str(network))
    return str(subnet)


def available_network_subnet(value):
    require(shutil.which("ip"), "The iproute2 ip command is required for --network-subnet")
    occupied = []
    identifiers = run(["docker", "network", "ls", "--quiet"], capture=True).stdout.split()
    for identifier in identifiers:
        network = docker_inspect("network", identifier)
        require(network is not None, "Docker networks changed during subnet validation; retry the check")
        for address in (network.get("IPAM", {}).get("Config") or []):
            occupied.append(("Docker network " + network.get("Name", identifier), address.get("Subnet")))
    routes = json.loads(run(["ip", "-j", "-4", "route", "show", "table", "all"], capture=True).stdout)
    require(isinstance(routes, list), "Host IPv4 route inventory is unavailable")
    occupied += [("host route", entry.get("dst")) for entry in routes
                 if entry.get("dst") not in (None, "", "default", "0.0.0.0/0")]
    return validate_network_subnet(value, occupied)


def prerequisites():
    require(sys.platform.startswith("linux") and os.geteuid() != 0,
            "Run as your ordinary Linux/WSL2 user, with Docker access; do not use sudo")
    require(sys.version_info >= (3, 11), "Python 3.11 or newer is required")
    for name in ("git", "docker"):
        require(shutil.which(name), name + " is required")
    run(["docker", "info", "--format", "{{.ServerVersion}}"], capture=True)
    run(["docker", "compose", "version"], capture=True)


def preflight(args):
    prerequisites()
    root = Path(args.dir).expanduser().absolute()
    require(not any(c in str(root) for c in ("\n", "\r", ",", '"')), "Unsupported installation path characters")
    ordinary(root.parent, directory=True)
    require(not os.path.lexists(root), "Installation directory already exists; existing servers are never overwritten")
    require(not str(root).startswith("/mnt/"), "Choose a runtime directory on the Linux filesystem, such as ~/coa-g1")
    manifest = release(args.manifest)
    paths = validate_data(manifest, args.data_dir, args.dbc_dir or Path(args.data_dir) / "dbc",
                          args.terrain_dir or args.data_dir)
    project = project_name(root, args.project)
    ports_available([args.auth_port, args.world_port])
    absent_resources(project)
    subnet = available_network_subnet(args.network_subnet) if args.network_subnet else None
    require(0 <= args.bots <= 1500, "Bot count must be between 0 and 1500")
    require(shutil.disk_usage(root.parent).free >= 30 * 1024**3, "At least 30 GiB free disk space is required")
    return {"schema_version": 1, "id": uuid.uuid4().hex, "root": str(root), "project": project,
            "release_id": manifest["release_id"], "release_manifest_sha256": digest(args.manifest),
            "data": paths, "ports": {"authserver": args.auth_port, "worldserver": args.world_port},
            "network_subnet": subnet,
            "bots": args.bots, "uid": os.getuid(), "gid": os.getgid(), "phase": "planned"}, manifest


def clone(pin, path):
    run(["git", "init", "--quiet", path])
    run(["git", "-C", path, "remote", "add", "origin", pin["repository"]])
    run(["git", "-C", path, "fetch", "--depth", "1", "origin", pin["revision"]])
    run(["git", "-C", path, "checkout", "--detach", "FETCH_HEAD"])
    require(run(["git", "-C", path, "rev-parse", "HEAD"], capture=True).stdout.strip() == pin["revision"],
            "Fetched revision differs from the release")


def prepare_sources(root, manifest):
    source = root / "source"
    clone(manifest["core"], source)
    module = source / "modules/mod-playerbots"
    require(not module.exists(), "Upstream unexpectedly contains the external Playerbots source")
    clone(manifest["playerbots"], module)
    for patch in manifest["patches"]:
        target = source if patch["target"] == "core" else module
        path = child(REPOSITORY, patch["path"])
        run(["git", "-C", target, "apply", "--check", path])
        run(["git", "-C", target, "apply", "--index", path])
        for relative, record in patch.get("files", {}).items():
            patched = ordinary(child(target, relative))
            require(digest(patched) == record["sha256"], "Applied source differs: " + relative)
            require(bool(patched.stat().st_mode & 0o111) == record["executable"],
                    "Applied source permissions differ: " + relative)
    for overlay in manifest["overlays"]:
        target = child(source, overlay["target"])
        require(not target.exists(), "Overlay would replace an upstream directory: " + overlay["target"])
        shutil.copytree(child(REPOSITORY, overlay["source"]), target)
        require(inventory(target) == overlay["files"], "Copied overlay differs")


def compose(root, *arguments, capture=False):
    state = load(root / "installation.json")
    return run(["docker", "compose", "--project-name", state["project"], "--file", root / "compose.json",
                *arguments], capture=capture)


def mount(source, target, readonly=True):
    return {"type": "bind", "source": str(source), "target": target, "read_only": readonly}


def service_mounts(root, state, writable=False):
    paths = state["data"]
    # Only the one-time build/bootstrap helper can access administrator credentials and backups.
    result = ([mount(root, "/g1", False)] if writable else
              [mount(root / name, "/g1/" + name) for name in ("build", "etc", "source")]
              + [mount(root / name, "/g1/" + name, False) for name in ("logs", "tmp")])
    result += [mount(paths["base"], "/g1/data"), mount(paths["dbc"], "/g1/data/dbc")]
    result.extend(mount(Path(paths["terrain"]) / name, "/g1/data/" + name) for name in ("maps", "vmaps", "mmaps"))
    return result


def composition(root, state, manifest):
    project, owner = state["project"], {OWNER: state["id"]}
    mysql = manifest["images"]["mysql"]
    require(re.fullmatch(r"mysql(?::[A-Za-z0-9_.-]+)?@sha256:[0-9a-f]{64}", mysql), "MySQL image must be digest-pinned")
    services = {"database": {"image": mysql, "container_name": project + "-database", "labels": owner,
        "restart": "unless-stopped", "env_file": [str(root / "state/database.env")],
        "volumes": [{"type": "volume", "source": "database", "target": "/var/lib/mysql"}],
        "healthcheck": {"test": ["CMD-SHELL", "MYSQL_PWD=\"$$MYSQL_ROOT_PASSWORD\" mysqladmin ping -h 127.0.0.1 -uroot --silent"],
                        "interval": "5s", "timeout": "10s", "retries": 60}}}
    for role in ("authserver", "worldserver"):
        services[role] = {"image": state["toolchain_image"], "container_name": project + "-" + role,
            "labels": owner, "user": str(state["uid"]) + ":" + str(state["gid"]),
            "entrypoint": ["/g1/build/src/server/apps/" + role], "command": ["-c", "/g1/etc/" + role + ".conf"],
            "restart": "unless-stopped", "stop_grace_period": "120s", "read_only": True,
            "stdin_open": role == "worldserver", "tty": role == "worldserver",
            "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"],
            "tmpfs": ["/tmp:rw,nosuid,nodev,size=128m"], "volumes": service_mounts(root, state),
            "ports": [{"target": 3724 if role == "authserver" else 8085,
                       "published": str(state["ports"][role]), "host_ip": "127.0.0.1", "protocol": "tcp"}]}
    network = {"name": project + "-network", "labels": owner}
    if state.get("network_subnet"):
        network["ipam"] = {"config": [{"subnet": validate_network_subnet(state["network_subnet"], [])}]}
    return {"name": project, "services": services,
            "volumes": {"database": {"name": project + "-database", "labels": owner}},
            "networks": {"default": network}}


def executor(root, state, action, *, network="none"):
    command = ["docker", "run", "--rm", "--network", network, "--user", f"{state['uid']}:{state['gid']}",
               "--label", OWNER + "=" + state["id"], "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
               "--env", "HOME=/tmp", "--env", "LUA51=/usr/bin/lua5.1", "--workdir", "/g1/source"]
    for item in service_mounts(root, state, writable=True):
        command += ["--mount", "type=bind,source=" + item["source"] + ",target=" + item["target"]
                    + (",readonly" if item["read_only"] else "")]
    command += ["--entrypoint", "python3", state["toolchain_image"], "-B", "/g1/control/g1-container.py", action]
    run(command)


def write_private(path, text):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)
    path.chmod(0o600)


def owned(root, *, ready=True):
    root = ordinary(root, directory=True)
    state = load(root / "installation.json")
    require(state["root"] == str(root) and re.fullmatch(r"[0-9a-f]{32}", state["id"]), "Installation identity mismatch")
    project_name(root, state["project"])
    if "compose_sha256" in state:
        require(digest(root / "compose.json") == state["compose_sha256"], "Compose file changed; review it before management")
        require(load(root / "compose.json")["name"] == state["project"], "Compose project changed")
    if ready:
        require(state["phase"] == "ready" and "compose_sha256" in state,
                "Installation is incomplete; inspect its state directory and command output before recovery")
        for name, wanted in state["binaries"].items():
            require(digest(root / "build" / name) == wanted, "Installed binary differs from its verified build")
    for kind, names in resource_names(state["project"]).items():
        for name in names:
            item = docker_inspect(kind, name)
            if item is not None:
                labels = (item.get("Labels") if kind != "container" else item["Config"].get("Labels")) or {}
                require(labels.get(OWNER) == state["id"], "Refusing an unrelated Docker resource: " + name)
    return root, state


def stop_failed_game(root, state):
    """Stop only this installation's game services after an unsuccessful startup."""
    if "compose_sha256" not in state:
        return
    owned(root, ready=False)
    roles = [role for role in ("worldserver", "authserver")
             if docker_inspect("container", state["project"] + "-" + role) is not None]
    if roles:
        compose(root, "stop", "--timeout", "120", *roles)


def wait_database(root, state):
    for _ in range(120):
        entry = docker_inspect("container", state["project"] + "-database")
        require(entry and entry["Config"]["Labels"].get(OWNER) == state["id"], "Database ownership changed")
        if entry["State"].get("Health", {}).get("Status") == "healthy":
            return
        require(entry["State"]["Running"], "Database exited before initialization")
        time.sleep(5)
    raise RuntimeError("Database did not become healthy; inspect installation logs")


def service_listener_ready(state, role):
    # Docker's host proxy can accept TCP before the process opens its internal listener.
    require(role in ("authserver", "worldserver"), "Unknown game service")
    port = 3724 if role == "authserver" else 8085
    try:
        result = subprocess.run(["docker", "exec", state["project"] + "-" + role, "python3", "-c",
            "import socket; socket.create_connection(('127.0.0.1'," + str(port) + "),1).close()"],
            capture_output=True, timeout=5)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def wait_game(root, state):
    for _ in range(120):
        ready = True
        for role in ("authserver", "worldserver"):
            entry = docker_inspect("container", state["project"] + "-" + role)
            require(entry and entry["Config"]["Labels"].get(OWNER) == state["id"], "Service ownership changed")
            require(not entry["State"].get("OOMKilled") and entry["RestartCount"] == 0,
                    "A game service crashed or restarted; inspect logs")
            ready &= entry["State"]["Running"]
            ready &= service_listener_ready(state, role)
            try:
                with socket.create_connection(("127.0.0.1", state["ports"][role]), timeout=1):
                    pass
            except OSError:
                ready = False
        if ready:
            return
        time.sleep(5)
    raise RuntimeError("Game listeners did not become ready; inspect logs")


def install(args):
    state, manifest = preflight(args)
    print(json.dumps({k: v for k, v in state.items() if k not in ("id", "uid", "gid")}, indent=2))
    if args.dry_run or args.command == "check":
        print("Preflight passed. No files, containers or databases were changed.")
        return
    root = Path(state["root"])
    root.mkdir(mode=0o700)
    for name in ("state", "control", "build", "install", "etc", "etc/modules", "logs", "tmp", "backups"):
        (root / name).mkdir(mode=0o700)
    shutil.copyfile(args.manifest, root / "state/release.json")
    shutil.copyfile(REPOSITORY / "docker/g1-container.py", root / "control/g1-container.py")
    save(root / "installation.json", state)
    try:
        prepare_sources(root, manifest)
        if args.toolchain_image:
            image = docker_inspect("image", args.toolchain_image)
            require(image is not None, "Requested prebuilt toolchain image is unavailable")
        else:
            tag = state["project"] + "-toolchain:" + manifest["release_id"]
            run(["docker", "build", "--file", REPOSITORY / "docker/g1-toolchain.Dockerfile", "--tag", tag,
                 REPOSITORY / "docker"])
            image = docker_inspect("image", tag)
        state["toolchain_image"] = image["Id"]
        save(root / "installation.json", state, replace=True)
        # The pinned upstream unit-test dependency is fetched during CMake configuration.
        # Database credentials and containers do not exist at this point.
        executor(root, state, "build", network="bridge")
        report = load(root / "state/verification/report.json")
        require(report["status"] == "passed" and all(report["stages"][name]["status"] == "passed"
                for name in ("source", "build", "unit")), "Build qualification did not pass")
        state["binaries"] = {name: digest(root / "build" / name) for name in
                             ("src/server/apps/worldserver", "src/server/apps/authserver", "src/tools/dbimport")}
        password = secrets.token_hex(32)
        write_private(root / "state/database.env", "MYSQL_ROOT_PASSWORD=" + password + "\nMYSQL_ROOT_HOST=%\n")
        write_private(root / "state/admin.cnf", "[client]\nhost=database\nuser=root\npassword=" + password + "\n")
        write_private(root / "state/runtime-password", secrets.token_hex(32) + "\n")
        save(root / "compose.json", composition(root, state, manifest))
        state["compose_sha256"] = digest(root / "compose.json")
        state["phase"] = "built"
        save(root / "installation.json", state, replace=True)
        absent_resources(state["project"])
        ports_available(list(state["ports"].values()))
        if state.get("network_subnet"):
            available_network_subnet(state["network_subnet"])
        compose(root, "config", "--quiet")
        run(["docker", "pull", manifest["images"]["mysql"]])
        compose(root, "up", "-d", "--no-build", "--pull", "never", "database")
        wait_database(root, state)
        state["phase"] = "bootstrap-started"
        save(root / "installation.json", state, replace=True)
        executor(root, state, "bootstrap", network=state["project"] + "-network")
        require(load(root / "state/bootstrap.json")["status"] == "passed", "Fresh bootstrap did not pass")
        state["phase"] = "ready"
        state["completed_utc"] = datetime.now(timezone.utc).isoformat()
        save(root / "installation.json", state, replace=True)
        compose(root, "create", "--no-build", "authserver", "worldserver")
        if not args.no_start:
            compose(root, "start", "authserver", "worldserver")
            wait_game(root, state)
        print("Installed " + manifest["release_id"] + ". Client realmlist: 127.0.0.1:" + str(args.auth_port))
        print("Source/build/unit qualification passed; gameplay and client acceptance are separate checks.")
    except BaseException:
        state["failed_phase"] = state["phase"]
        state["phase"] = "incomplete"
        save(root / "installation.json", state, replace=True)
        try:
            stop_failed_game(root, state)
        except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
            print("Could not stop this installation's game services: " + str(error), file=sys.stderr)
        print("Installation stopped. Partial files and its isolated database were retained; no automatic retry or deletion.",
              file=sys.stderr)
        raise


def backup(root, state):
    for role in ("authserver", "worldserver"):
        service = docker_inspect("container", state["project"] + "-" + role)
        require(service is not None and not service["State"]["Running"],
                "Stop the game services before backup: g1.py stop --dir " + str(root))
    database = docker_inspect("container", state["project"] + "-database")
    require(database and database["State"]["Running"], "Start this installation's database before backup")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    target = root / "backups" / (stamp + ".sql.gz")
    command = ["docker", "exec", state["project"] + "-database", "sh", "-c",
               'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysqldump --user=root --lock-all-tables --quick '
               '--routines --events --triggers --hex-blob --set-gtid-purged=OFF --no-tablespaces '
               '--column-statistics=0 --databases ' + " ".join(SCHEMAS)]
    tail = b""
    try:
        with target.with_suffix(".log").open("xb") as errors, target.open("xb") as destination, \
                gzip.GzipFile(fileobj=destination, mode="wb") as archive:
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors) as process:
                try:
                    while chunk := process.stdout.read(1024 * 1024):
                        archive.write(chunk)
                        tail = (tail + chunk)[-8192:]
                    require(process.wait() == 0, "Database dump failed; partial archive retained")
                except BaseException:
                    process.kill()
                    process.wait()
                    raise
        require(b"-- Dump completed on " in tail, "Database dump is incomplete")
        save(target.with_suffix(".json"), {"archive_sha256": digest(target), "release_id": state["release_id"],
            "installation_id": state["id"], "database_id": database["Id"], "created_utc": stamp,
            "game_services_stopped": True, "global_read_lock": True, "restore_tested": False})
    finally:
        if target.exists():
            target.chmod(0o600)
    print("Backup saved: " + str(target))


def manage(args):
    prerequisites()
    root, state = owned(Path(args.dir).expanduser(), ready=args.command not in ("status", "stop", "logs"))
    if args.command != "status":
        require("compose_sha256" in state, "No Docker services were created for this incomplete installation")
    if args.command == "status":
        print("Release: " + state["release_id"] + "; installation phase: " + state["phase"])
        if "compose_sha256" in state:
            compose(root, "ps", "--all")
    elif args.command == "start":
        compose(root, "start", "database")
        wait_database(root, state)
        compose(root, "start", "authserver", "worldserver")
        try:
            wait_game(root, state)
        except BaseException:
            stop_failed_game(root, state)
            raise
    elif args.command == "stop":
        compose(root, "stop", "--timeout", "120", "worldserver", "authserver")
        if args.database:
            compose(root, "stop", "--timeout", "120", "database")
    elif args.command == "logs":
        compose(root, "logs", "--tail", "100", *( ["--follow"] if args.follow else []), "authserver", "worldserver")
    elif args.command == "backup":
        backup(root, state)
    elif args.command == "console":
        print("Detach without stopping the server: Ctrl+P, then Ctrl+Q. Do not press Ctrl+C.")
        run(["docker", "attach", "--sig-proxy=false", state["project"] + "-worldserver"])
    elif args.command == "update-check":
        manifest = load(root / "state/release.json")
        result = run(["git", "ls-remote", manifest["core"]["repository"], "refs/heads/main"], capture=True)
        fields = result.stdout.split()
        require(fields and COMMIT.fullmatch(fields[0]), "Upstream did not return an exact main revision")
        print(json.dumps({"installed_release": state["release_id"], "installed_upstream": manifest["core"]["revision"],
                          "available_upstream": fields[0], "new_upstream_commits": fields[0] != manifest["core"]["revision"],
                          "action": "Review a qualified community release before updating; no files or services changed."}, indent=2))


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("check", "install"):
        command = commands.add_parser(name)
        command.add_argument("--dir", required=True, help="New runtime directory on the Linux filesystem")
        command.add_argument("--manifest", type=Path, default=REPOSITORY / "releases/g1-20261029/manifest.json")
        command.add_argument("--data-dir", type=Path, required=True)
        command.add_argument("--dbc-dir", type=Path)
        command.add_argument("--terrain-dir", type=Path)
        command.add_argument("--project")
        command.add_argument("--network-subnet", help="Optional unused RFC1918 IPv4 /24 for the private Docker network")
        command.add_argument("--auth-port", type=int, default=33727)
        command.add_argument("--world-port", type=int, default=38088)
        command.add_argument("--bots", type=int, default=1000, help="Online population (default: tested G1 target of 1000)")
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--no-start", action="store_true")
        command.add_argument("--toolchain-image", help="Existing compatible Docker toolchain image for an expert build")
    for name in ("status", "start", "stop", "logs", "backup", "update-check", "console"):
        command = commands.add_parser(name)
        command.add_argument("--dir", required=True)
        if name == "stop":
            command.add_argument("--database", action="store_true", help="Also stop the retained database service")
        if name == "logs":
            command.add_argument("--follow", action="store_true")
    return result


def main():
    os.umask(0o077)
    args = parser().parse_args()
    try:
        (install if args.command in ("check", "install") else manage)(args)
    except (RuntimeError, OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        print("G1: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
