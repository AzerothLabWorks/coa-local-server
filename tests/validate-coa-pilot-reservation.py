#!/usr/bin/env python3
"""Exercise exact pilot reservation and account assignment code with DB/cache doubles."""

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
    source = (args.module / "src/Bot/RandomPlayerbotMgr.cpp").read_text(encoding="utf-8")
    production = "\n\n".join([
        definition(source, "std::set<uint32> GetReservedCoaTestPilotAccounts("),
        definition(source, "void RandomPlayerbotMgr::AssignAccountTypes()"),
    ])
    with tempfile.TemporaryDirectory(prefix="coa-pilot-reservation-") as directory:
        temporary = Path(directory)
        (temporary / "CoaPilotReservationProduction.h").write_text(production + "\n", encoding="utf-8")
        executable = temporary / "coa-pilot-reservation"
        command = shlex.split(os.environ.get("CXX", "c++")) + [
            # GCC 7 flags an unused member of an existing upstream structured binding.
            "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-error=unused-variable", "-I", str(temporary),
            "-I", str(args.module / "src/Bot"),
            str(Path(__file__).with_name("coa-pilot-reservation.cpp")), "-o", str(executable),
        ]
        subprocess.run(command, check=True)
        environment = dict(os.environ, COA_TEST_PILOT_NAMES=" amaryla , ELOWEN ")
        subprocess.run([str(executable)], check=True, env=environment)
    print("COA pilot reservation: actual helper and both account-assignment paths passed.")


if __name__ == "__main__":
    main()
