#!/usr/bin/env python3
"""Test real COA combat triggers and mount-usefulness gates with API doubles."""

import argparse
import os
from pathlib import Path
import re
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
    parser.add_argument("module", type=Path, help="patched mod-playerbots directory")
    args = parser.parse_args()
    source = args.module / "src"
    coa = (source / "Ai/Class/Coa/CoaAiObjectContext.cpp").read_text(encoding="utf-8")
    strategy = (source / "Bot/Engine/Strategy/Strategy.h").read_text(encoding="utf-8")
    combat_header = (source / "Ai/Base/Strategy/CombatStrategy.h").read_text(encoding="utf-8")
    combat_source = (source / "Ai/Base/Strategy/CombatStrategy.cpp").read_text(encoding="utf-8")
    mount = (source / "Ai/Base/Actions/CheckMountStateAction.cpp").read_text(encoding="utf-8")

    constants = [definition(strategy, "enum StrategyType : uint32") + ";"]
    constants += re.findall(r"static constexpr float ACTION_[A-Z_]+\s*=[^;]+;", strategy)
    definitions = [
        definition(combat_header, "class CombatStrategy : public Strategy") + ";",
        definition(combat_source, "void CombatStrategy::InitTriggers"),
        definition(coa, "class CoaCombatStrategy final : public") + ";",
        definition(coa, "class CoaBrewingStrategy final : public") + ";",
        definition(mount, "bool CheckMountStateAction::isUseful()"),
        definition(mount, "bool CheckMountStateAction::ShouldFollowMasterMountState"),
        definition(mount, "bool CheckMountStateAction::ShouldDismountForMaster"),
    ]

    with tempfile.TemporaryDirectory(prefix="coa-travel-test-") as directory:
        temporary = Path(directory)
        (temporary / "CoaTravelConstants.h").write_text("\n\n".join(constants) + "\n", encoding="utf-8")
        (temporary / "CoaTravelProduction.h").write_text("\n\n".join(definitions) + "\n", encoding="utf-8")
        executable = temporary / "coa-travel"
        command = shlex.split(os.environ.get("CXX", "c++")) + [
            "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(temporary),
            str(Path(__file__).with_name("coa-travel.cpp")), "-o", str(executable),
        ]
        subprocess.run(command, check=True)
        subprocess.run([str(executable)], check=True)
    print("COA production combat-trigger and mount-usefulness regression checks passed.")


if __name__ == "__main__":
    main()
