#!/usr/bin/env python3
"""Read-only audit of the reference G1 twenty-character configuration."""

import argparse
import json
import re
from pathlib import Path


EXPECTED = {
    "CharactersPerRealm": 20,
    "CharactersPerAccount": 128,
    "CoA.CharacterSelectionEnable": 1,
    "CoA.CharacterSelectionMaxActive": 20,
}
ASSIGNMENT = re.compile(r"^\s*([\w.]+)\s*=(.*)$")
INTEGER = re.compile(r'''\s*(?:"([0-9]+)"|([0-9]+))\s*(?:#.*)?$''')


def audit(world_config, coa_config):
    paths = [Path(world_config), Path(coa_config)]
    result = {
        "status": "passed",
        "scope": "configuration-files-only",
        "files": [str(path) for path in paths],
        "expected": EXPECTED.copy(),
        "observed": {},
        "issues": [],
        "limitations": [
            "Confirm these files are loaded by the selected runtime and review environment/other config overrides.",
            "This audit does not query rosters, verify the running process, or test native client selection.",
        ],
    }
    try:
        if paths[0].resolve() == paths[1].resolve():
            raise ValueError("Supply distinct worldserver.conf and module coa.conf paths.")
        contents = [path.read_text(encoding="utf-8-sig") for path in paths]
    except (OSError, UnicodeError, ValueError) as error:
        result["status"] = "unavailable"
        result["issues"].append(f"Cannot audit configuration files: {type(error).__name__}.")
        return result

    assignments = {key: [] for key in EXPECTED}
    for path, content in zip(paths, contents):
        for number, line in enumerate(content.splitlines(), 1):
            match = ASSIGNMENT.fullmatch(line)
            if not match or match[1] not in EXPECTED:
                continue
            scalar = INTEGER.fullmatch(match[2])
            try:
                value = int(scalar[1] or scalar[2]) if scalar else None
            except ValueError:
                value = None
            assignments[match[1]].append((value, str(path), number))

    for key, expected in EXPECTED.items():
        rows = assignments[key]
        if len(rows) != 1:
            reason = "missing" if not rows else "assigned more than once"
            result["issues"].append(f"{key} is {reason}; resolve the loaded configuration explicitly.")
            continue
        value, path, number = rows[0]
        if value is None:
            result["issues"].append(f"{key} must be a decimal integer ({path}:{number}).")
            continue
        result["observed"][key] = value
        if value != expected:
            result["issues"].append(f"{key} is {value}; the preserved G1 setting is {expected}.")
    if result["issues"]:
        result["status"] = "failed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("audit", help="Check files without changing configuration or services")
    command.add_argument("--world-config", required=True, type=Path)
    command.add_argument("--coa-config", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.world_config, args.coa_config)
    print(json.dumps(result, indent=2))
    return {"passed": 0, "failed": 2, "unavailable": 3}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
