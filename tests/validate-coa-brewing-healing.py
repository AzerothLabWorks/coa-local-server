#!/usr/bin/env python3
"""Compile/test actual Brewing action code with small deterministic API doubles."""

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
    parser.add_argument("module", type=Path, help="patched mod-playerbots source directory")
    args = parser.parse_args()
    source = (args.module / "src/Ai/Class/Coa/CoaAiObjectContext.cpp").read_text(encoding="utf-8")
    pieces = [re.search(r"constexpr float BREWING_HEAL_BELOW_PCT[^;]*;", source).group()]
    for name in ("LOAS_BREW", "SPIRIT_IN_A_BOTTLE", "POTION_TOSS"):
        pieces.append(re.search(r"constexpr std::array<uint32, \d+> " + name + r"\s*=\s*\{[^}]*\};", source).group())
    pieces.append(definition(source, "Player* FindBrewingHealTarget(Player* bot)"))
    pieces.append(definition(source, "template <std::size_t N>\nbool CastFirstAvailableHeal"))
    pieces.append(definition(source, "class CoaBrewingHealAction final : public Action") + ";")

    with tempfile.TemporaryDirectory(prefix="coa-brewing-test-") as directory:
        temporary = Path(directory)
        (temporary / "CoaBrewingProduction.h").write_text("\n\n".join(pieces) + "\n", encoding="utf-8")
        executable = temporary / "coa-brewing-healing"
        command = shlex.split(os.environ.get("CXX", "c++")) + [
            "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(temporary),
            str(Path(__file__).with_name("coa-brewing-healing.cpp")), "-o", str(executable),
        ]
        subprocess.run(command, check=True)
        subprocess.run([str(executable)], check=True)
    print("Brewing production rank, threshold, cooldown and target-selection checks passed.")


if __name__ == "__main__":
    main()
