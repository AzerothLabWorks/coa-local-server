#!/usr/bin/env python3
"""Compile the production pilot-preparation handler against deterministic API doubles."""

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def handler_definition(source):
    start = source.index("static bool HandleLocalBotPrepareCommand(")
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    # The handler's string placeholders have balanced braces. Extract its exact
    # body instead of reproducing its safety decisions in Python or the doubles.
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path,
                        help="optional patched full core source directory; default: repository patch")
    args = parser.parse_args()
    if args.source:
        source_file = args.source / "modules/mod-ascension-compat/src/AscensionCompat.cpp"
        source = source_file.read_text(encoding="utf-8")
    else:
        patch = Path(__file__).resolve().parent.parent / "source-patches/coa-bot-pilot-prepare.patch"
        # Every line of this new handler is an addition in the release patch.
        source = "\n".join(line[1:] for line in patch.read_text(encoding="utf-8").splitlines()
                           if line.startswith("+") and not line.startswith("+++"))

    with tempfile.TemporaryDirectory(prefix="coa-pilot-prepare-test-") as directory:
        temporary = Path(directory)
        (temporary / "CoaPilotPrepareProduction.h").write_text(handler_definition(source) + "\n", encoding="utf-8")
        executable = temporary / "coa-pilot-prepare"
        command = shlex.split(os.environ.get("CXX", "c++")) + [
            "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(temporary),
            str(Path(__file__).with_name("coa-pilot-prepare.cpp")), "-o", str(executable),
        ]
        subprocess.run(command, check=True)
        subprocess.run([str(executable)], check=True)
    print("Production pilot-preparation guard, level-up, retry, synchronization and save checks passed.")


if __name__ == "__main__":
    main()
