#!/usr/bin/env python3
"""Exercise the production COA talent record, command and snapshot methods."""

import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


def definition(source, marker):
    """Extract a full definition without counting braces inside strings/comments."""
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    tokens = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]', re.S)
    for match in tokens.finditer(source, opening):
        token = match.group()
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
            if depth == 0:
                return source[start:match.end()]
    raise ValueError("Unclosed definition: " + marker)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="patched full core source directory")
    args = parser.parse_args()
    source = (args.source / "modules/mod-ascension-compat/src/AscensionCompat.cpp").read_text(encoding="utf-8")
    service_markers = [
        "static uint32 GetRecordedTalentRank(",
        "static void RecordTalentSelection(",
        "static void ClearRecordedTalentSelections(",
        "void SendTalentState(",
        "uint32 GetActiveSpecialization(",
        "bool SwitchSpecialization(",
    ]
    methods = "\n\n".join(definition(source, marker) for marker in service_markers)
    commands = "\n\n".join(definition(source, marker) for marker in [
        "static bool HandleLocalTalentCommand(",
        "static bool HandleLocalSpecStateCommand(",
    ])
    constants = "\n".join(value for value in re.findall(
        r'constexpr char ASCENSION_[A-Z_]+(?:\[\])?\s*=\s*"[^"\n]*";', source)
        if re.search(r'ASCENSION_[A-Z_]+', value).group() in methods + commands)

    # A snapshot query is observational: never repair, learn, infer from spells,
    # or use the setting getter that creates a missing entry as a side effect.
    query = definition(source, "void SendTalentState(")
    read_rank = definition(source, "static uint32 GetRecordedTalentRank(")
    for forbidden in ("GetPlayerSetting(", "UpdatePlayerSetting(", "learnSpell(", "removeSpell(",
                      "SynchronizeProgression(", "HasSpell(", "GetSpellMap("):
        assert forbidden not in query + read_rank, "Snapshot must be read-only: " + forbidden

    with tempfile.TemporaryDirectory(prefix="coa-talent-state-test-") as directory:
        temporary = Path(directory)
        (temporary / "CoaTalentStateConstants.h").write_text(constants + "\n", encoding="utf-8")
        (temporary / "CoaTalentStateService.h").write_text(methods + "\n", encoding="utf-8")
        (temporary / "CoaTalentStateCommands.h").write_text(commands + "\n", encoding="utf-8")
        executable = temporary / "coa-talent-state"
        command = shlex.split(os.environ.get("CXX", "c++")) + [
            "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(temporary),
            str(Path(__file__).with_name("coa-talent-state.cpp")), "-o", str(executable),
        ]
        subprocess.run(command, check=True)
        subprocess.run([str(executable)], check=True)
    print("Production COA talent persistence, explicit edits, refunds and read-only snapshot checks passed.")


if __name__ == "__main__":
    main()
