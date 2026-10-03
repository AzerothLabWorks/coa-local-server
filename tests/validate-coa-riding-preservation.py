#!/usr/bin/env python3
"""Test the actual InitSkills implementation against deterministic player API doubles."""

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def definition(source, marker):
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", type=Path, help="patched mod-playerbots source directory")
    args = parser.parse_args()
    source = (args.module / "src/Bot/Factory/PlayerbotFactory.cpp").read_text(encoding="utf-8")
    production = definition(source, "void PlayerbotFactory::InitSkills()")
    # These real callers all reach the same protected entry point. Tests below
    # execute it directly; they do not simulate unrelated refresh operations.
    assert "InitSkills();" in definition(source, "void PlayerbotFactory::Refresh()")
    with tempfile.TemporaryDirectory(prefix="coa-riding-preservation-") as directory:
        temporary = Path(directory)
        (temporary / "CoaRidingProduction.h").write_text(production + "\n", encoding="utf-8")
        executable = temporary / "coa-riding-preservation"
        command = shlex.split(os.environ.get("CXX", "c++")) + [
            "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(temporary),
            str(Path(__file__).with_name("coa-riding-preservation.cpp")), "-o", str(executable),
        ]
        subprocess.run(command, check=True)
        subprocess.run([str(executable)], check=True)
    print("COA riding preservation: exact production InitSkills regression checks passed.")


if __name__ == "__main__":
    main()
