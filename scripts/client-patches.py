#!/usr/bin/env python3
"""Prepare, install, or roll back the reviewed G1 client compatibility repairs."""

import argparse
import csv
from datetime import datetime, timezone
import difflib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
PATCHES = ROOT / "client-patches"
MANIFEST = PATCHES / "g1-client-manifest.json"
METADATA = {"(attributes)", "(listfile)"}
GAME_PROCESSES = {"ascension.exe", "wow.exe", "wow-64.exe", "mmgr64.exe"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def plain(path):
    path = Path(os.path.abspath(path))
    for candidate in (path, *path.parents):
        if os.path.lexists(candidate):
            info = candidate.lstat()
            require(not stat.S_ISLNK(info.st_mode)
                    and not getattr(info, "st_file_attributes", 0) & 0x400,
                    "Linked/reparse path refused: " + str(candidate))
    return path


def sha(path):
    with plain(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(value):
    require(isinstance(value, str) and value and "\\" not in value
            and ":" not in value and "\x00" not in value, "Unsafe relative path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(x not in (".", "..", "") for x in value.split("/")),
            "Unsafe relative path")
    require(all(not x.endswith((".", " ")) and not re.fullmatch(
        r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", x) for x in path.parts),
        "Windows path alias refused")
    return path


def beneath(root, name):
    root = plain(root)
    result = plain(root.joinpath(*relative(name).parts))
    require(result.is_relative_to(root) and result != root, "Path escaped its root")
    return result


def tree(root):
    root = plain(root)
    require(root.is_dir(), "Expected directory: " + str(root))
    result = {}
    for path in sorted(root.rglob("*")):
        plain(path)
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha(path)
        else:
            require(path.is_dir(), "Unsupported filesystem entry")
    return result


def read_json(path):
    return json.loads(plain(path).read_text(encoding="utf-8"))


def save(path, data):
    with plain(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def now():
    return datetime.now(timezone.utc).isoformat()


def require_closed():
    require(os.name == "nt", "Install/rollback must run in native Windows Python, not WSL")
    output = subprocess.run(["tasklist.exe", "/FO", "CSV", "/NH"], check=True,
                            capture_output=True, text=True).stdout
    running = {row[0].lower() for row in csv.reader(io.StringIO(output)) if row}
    require(not running & GAME_PROCESSES, "Fully close all game clients and MMgr64 first")


def source_inventory(manifest):
    names = {"g1-client-manifest.json"}
    for item in [*manifest["members"].values(), *manifest["optional_loose"].values()]:
        names.update(item[key] for key in ("patch", "replacement") if key in item)
        names.update(item.get("alternate_patch", {}).values())
    return {name: sha(beneath(PATCHES, name)) for name in sorted(names)}


def protected_identity(client, manifest):
    result = {name: sha(beneath(client, name)) for name in manifest["protected_identity"]}
    require(result == manifest["protected_identity"],
            "Unsupported client executable/extension version; no files changed")
    return result


def patch_sections(data):
    sections = {}
    current = None
    old, new = [], []
    old_count = new_count = None

    def finish():
        if old_count is not None:
            require(len(old) == old_count and len(new) == new_count, "Malformed patch hunk")
            sections[current].append(("".join(old), "".join(new)))

    for line in data.replace("\r\n", "\n").splitlines(keepends=True):
        if line.startswith("--- "):
            finish()
            old, new, old_count, new_count = [], [], None, None
            name = line[4:].strip()
            require(name.startswith("a/"), "Unsupported patch source")
            current = str(relative(name[2:]))
            require(current not in sections, "Duplicate patch file")
            sections[current] = []
        elif line.startswith("+++ "):
            require(line[4:].strip() == "b/" + current, "Patch renames are unsupported")
        elif line.startswith("@@ "):
            finish()
            match = re.match(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@", line)
            require(match is not None and current is not None, "Malformed hunk header")
            old_count, new_count = (int(x or 1) for x in match.groups())
            old, new = [], []
        elif line.startswith(("diff --git ", "index ")):
            continue
        elif old_count is not None:
            require(line[0] in " +-", "Unsupported patch line")
            if line[0] != "+":
                old.append(line[1:])
            if line[0] != "-":
                new.append(line[1:])
        elif not line.strip():
            continue
        else:
            raise ValueError("Unsupported unified patch")
    finish()
    require(sections and all(sections.values()), "Empty patch")
    return sections


def transform(data, item, member):
    before = digest(data)
    if before == item["after"]:
        return data
    alternative = item.get("alternate_patch", {}).get(before)
    require(before in item["before"] or alternative, "Unsupported input member: " + member)
    if "replacement" in item:
        output = beneath(PATCHES, item["replacement"]).read_bytes().replace(b"\r\n", b"\n")
    else:
        patch = beneath(PATCHES, alternative or item["patch"]).read_text(encoding="utf-8")
        sections = patch_sections(patch)
        require(member in sections, "Member missing from patch")
        lines = data.decode("utf-8").splitlines(keepends=True)
        for old, new in sections[member]:
            old_lines, new_lines = old.splitlines(keepends=True), new.splitlines(keepends=True)
            normalized = [line.replace("\r\n", "\n") for line in lines]
            matches = [i for i in range(len(lines) - len(old_lines) + 1)
                       if normalized[i:i + len(old_lines)] == old_lines]
            require(old_lines and len(matches) == 1, "Patch context absent or ambiguous: " + member)
            start = matches[0]
            original = lines[start:start + len(old_lines)]
            replacement = []
            for operation, a, b, c, d in difflib.SequenceMatcher(
                    a=old_lines, b=new_lines, autojunk=False).get_opcodes():
                if operation == "equal":
                    replacement.extend(original[a:b])
                elif operation in ("insert", "replace"):
                    nearby = original[min(a, len(original) - 1)]
                    newline = "\r\n" if nearby.endswith("\r\n") else "\n"
                    replacement.extend(line.replace("\n", newline) for line in new_lines[c:d])
            lines[start:start + len(old_lines)] = replacement
        output = "".join(lines).encode("utf-8")
    require(digest(output) == item["after"], "Patched member differs from qualified output: " + member)
    return output


class Mpq:
    def __init__(self, tool, expected):
        self.tool = plain(tool)
        self.expected = expected
        require(sha(self.tool) == expected, "MPQ tool does not match the reviewed Windows build")

    def call(self, *args):
        require(sha(self.tool) == self.expected, "MPQ tool changed")
        result = subprocess.run([str(self.tool), *map(str, args)], capture_output=True, text=True)
        require(result.returncode == 0, "MPQ " + str(args[0]) + " failed: "
                + (result.stderr or result.stdout).strip()[-2000:])
        return result.stdout

    def names(self, archive, count):
        names = self.call("list", "--all", archive).splitlines()
        require(len(names) == count and len({x.lower() for x in names}) == count,
                "Archive has an unexpected member count or colliding names")
        for name in names:
            require("/" not in name, "Unexpected MPQ separator")
            relative(name.replace("\\", "/"))
        require(METADATA.issubset(names), "MPQ metadata missing")
        return sorted(names)

    def extract(self, archive, destination, names):
        extract_paths(destination, names)
        require(not destination.exists(), "Extraction directory exists")
        destination.mkdir()
        self.call("extract", "--keep", "--output", destination, archive)
        inventory = tree(destination)
        require(set(inventory) == {x.replace("\\", "/") for x in names},
                "Extraction has unexpected or missing files")
        return inventory


def extract_paths(destination, names):
    for name in names:
        path = beneath(destination, name.replace("\\", "/"))
        require(len(str(path)) < 260,
                "The reviewed MPQ utility requires shorter extraction paths; choose a shorter artifact directory")


def prepare(args):
    require(os.name == "nt", "This MPQ recipe requires native Windows Python and the reviewed Windows tool")
    client, artifacts = plain(args.client), plain(args.artifacts)
    require(client.is_dir() and artifacts.parent.is_dir() and not os.path.lexists(artifacts),
            "Use an existing client and a new artifact directory")
    require(not artifacts.is_relative_to(client) and not client.is_relative_to(artifacts),
            "Keep artifacts outside the client")
    require(client.drive.lower() == artifacts.drive.lower(), "Keep artifacts on the same drive for recoverable addon moves")
    manifest = read_json(MANIFEST)
    identity = protected_identity(client, manifest)
    archive = beneath(client, manifest["archive"])
    initial_hash = sha(archive)
    require(initial_hash in manifest["accepted_archive_sha256"],
            "Unknown patch-B.MPQ fingerprint; refuse instead of overwriting another client version")
    mpq = Mpq(args.mpq_tool, manifest["mpqcli"]["windows_sha256"])
    source = source_inventory(manifest)
    names = mpq.names(archive, manifest["archive_members"])
    for directory in ("before-extracted", "after-extracted"):
        extract_paths(artifacts / directory, names)
    loose = {}
    for name, item in manifest["optional_loose"].items():
        path = beneath(client, name)
        if path.exists():
            data = path.read_bytes()
            loose[name] = (data, transform(data, item, item.get("patch_member", name)))
    helper = beneath(client, manifest["retire_addon"])
    helper_state = tree(helper) if helper.exists() else None
    artifacts.mkdir(mode=0o700)
    backup, candidate = artifacts / "archive.before.mpq", artifacts / "archive.prepared.mpq"
    shutil.copyfile(archive, backup)
    shutil.copyfile(backup, candidate)
    require(sha(backup) == sha(candidate) == initial_hash, "Archive changed during copying")
    before = mpq.extract(backup, artifacts / "before-extracted", names)
    changes = []
    for name, item in manifest["members"].items():
        data = beneath(artifacts / "before-extracted", name).read_bytes()
        output = transform(data, item, name)
        if output != data:
            replacement = artifacts / ("member-" + str(len(changes)))
            replacement.write_bytes(output)
            mpq.call("add", "--overwrite", "--path", name.replace("/", "\\"), candidate, replacement)
            changes.append(name)
    require(mpq.names(candidate, manifest["archive_members"]) == names, "Archive member identities changed")
    after = mpq.extract(candidate, artifacts / "after-extracted", names)
    for name in before:
        if name in manifest["members"]:
            require(after[name] == manifest["members"][name]["after"], "Unexpected modified member")
        elif name not in METADATA:
            require(after[name] == before[name], "Unrelated archive member changed: " + name)
    entries = [{"target": manifest["archive"], "before": initial_hash, "after": sha(candidate),
                "backup": backup.name, "prepared": candidate.name}]
    for index, (name, (old, new)) in enumerate(loose.items()):
        old_name, new_name = f"loose-{index}.before", f"loose-{index}.prepared"
        (artifacts / old_name).write_bytes(old)
        (artifacts / new_name).write_bytes(new)
        entries.append({"target": name, "before": digest(old), "after": digest(new),
                        "backup": old_name, "prepared": new_name})
    require(sha(archive) == initial_hash and protected_identity(client, manifest) == identity,
            "Client changed during preparation")
    require(all(sha(beneath(client, name)) == digest(value[0]) for name, value in loose.items()),
            "WeakAuras changed during preparation")
    require((tree(helper) if helper.exists() else None) == helper_state, "Retired helper changed")
    require(source_inventory(manifest) == source, "Patch inputs changed during preparation")
    proof = {"schema": 1, "status": "prepared", "client": str(client), "artifacts": str(artifacts),
             "manifest_id": manifest["id"], "source": source, "script_sha256": sha(__file__),
             "identity": identity, "entries": entries, "helper": helper_state,
             "changed_members": changes, "member_count": len(names),
             "unchanged_ordinary_members": len(names) - len(changes) - len(METADATA), "utc": now()}
    save(artifacts / "prepared.json", proof)
    print(json.dumps({"status": "prepared-not-installed", "artifacts": str(artifacts),
                      "changed_members": changes, "no_client_files_changed": True}, indent=2))


def load_proof(args):
    client, artifacts = plain(args.client), plain(args.artifacts)
    manifest, proof = read_json(MANIFEST), read_json(artifacts / "prepared.json")
    require(str(client) == proof["client"] and str(artifacts) == proof["artifacts"]
            and proof["schema"] == 1 and proof["status"] == "prepared"
            and proof["manifest_id"] == manifest["id"] and proof["script_sha256"] == sha(__file__)
            and proof["source"] == source_inventory(manifest), "Prepared package identity changed")
    require(not artifacts.is_relative_to(client) and not client.is_relative_to(artifacts), "Overlapping roots")
    protected_identity(client, manifest)
    allowed = {manifest["archive"], *manifest["optional_loose"]}
    targets = [entry["target"] for entry in proof["entries"]]
    require(len(set(targets)) == len(targets) and set(targets).issubset(allowed)
            and manifest["archive"] in targets, "Unexpected replacement targets")
    for entry in proof["entries"]:
        require(sha(beneath(artifacts, entry["backup"])) == entry["before"]
                and sha(beneath(artifacts, entry["prepared"])) == entry["after"], "Prepared files changed")
    return client, artifacts, manifest, proof


def replace_file(target, source, before, after):
    target = plain(target)
    require(sha(target) == before and sha(source) == after, "Replacement input changed")
    temporary = target.with_name(target.name + ".coa-" + uuid.uuid4().hex + ".tmp")
    with source.open("rb") as incoming, temporary.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
        outgoing.flush()
        os.fsync(outgoing.fileno())
    try:
        require(sha(temporary) == after and sha(target) == before, "File changed before replacement")
        require_closed()
        os.replace(temporary, target)
        require(sha(target) == after, "Replacement verification failed")
    finally:
        if temporary.exists():
            plain(temporary).unlink()


def install(args):
    require_closed()
    client, artifacts, manifest, proof = load_proof(args)
    require(not (artifacts / "attempt.json").exists(), "Install already attempted; use rollback or a new preparation")
    for entry in proof["entries"]:
        require(sha(beneath(client, entry["target"])) == entry["before"], "Client changed after preparation")
    helper, retired = beneath(client, manifest["retire_addon"]), artifacts / "retired-helper"
    require((tree(helper) if helper.exists() else None) == proof["helper"] and not retired.exists(),
            "Retired addon changed after preparation")
    save(artifacts / "attempt.json", {"prepared_sha256": sha(artifacts / "prepared.json"), "utc": now()})
    try:
        for entry in proof["entries"]:
            if entry["before"] != entry["after"]:
                replace_file(beneath(client, entry["target"]), beneath(artifacts, entry["prepared"]),
                             entry["before"], entry["after"])
        if proof["helper"] is not None:
            require_closed()
            require(tree(helper) == proof["helper"], "Retired addon changed")
            os.replace(helper, retired)
        require(all(sha(beneath(client, x["target"])) == x["after"] for x in proof["entries"]),
                "Final installed hash mismatch")
        protected_identity(client, manifest)
        save(artifacts / "installed.json", {"status": "installed", "utc": now(),
             "prepared_sha256": sha(artifacts / "prepared.json")})
        print("Compatibility repairs installed. Keep the artifact directory for rollback.")
    except Exception as error:
        save(artifacts / "failed.json", {"error": str(error), "utc": now(),
             "recovery": "Keep the client closed and run rollback with this same artifact directory."})
        raise


def rollback(args):
    require_closed()
    client, artifacts, manifest, proof = load_proof(args)
    require(read_json(artifacts / "attempt.json")["prepared_sha256"] == sha(artifacts / "prepared.json"),
            "Install attempt does not match preparation")
    require(not (artifacts / "rolled-back.json").exists(), "Already rolled back")
    for entry in proof["entries"]:
        require(sha(beneath(client, entry["target"])) in (entry["before"], entry["after"]),
                "A client file changed since installation; preserve it for manual review")
    helper, retired = beneath(client, manifest["retire_addon"]), artifacts / "retired-helper"
    if proof["helper"] is not None:
        require((retired.exists() and not helper.exists() and tree(retired) == proof["helper"])
                or (helper.exists() and not retired.exists() and tree(helper) == proof["helper"]),
                "Retired addon cannot be safely restored")
    for entry in reversed(proof["entries"]):
        target = beneath(client, entry["target"])
        if entry["before"] != entry["after"] and sha(target) == entry["after"]:
            replace_file(target, beneath(artifacts, entry["backup"]), entry["after"], entry["before"])
    if proof["helper"] is not None and retired.exists():
        require_closed()
        plain(helper.parent)
        os.replace(retired, helper)
    save(artifacts / "rolled-back.json", {"status": "rolled-back", "utc": now()})
    print("Restored the operation's original files; saved variables and other addons were not replaced.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "install", "rollback"))
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--mpq-tool", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(args.mpq_tool is not None, "prepare requires --mpq-tool")
    globals()[args.action](args)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("Client repair stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
