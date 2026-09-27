#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${1:?Usage: validate-coa-ai.sh PATCHED_CORE_SOURCE}"
MODULE="$SOURCE/modules/mod-playerbots"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
read -r -a compiler <<< "${CXX:-c++}"

"${compiler[@]}" -std=c++17 -Wall -Wextra -Werror -fsyntax-only \
  -I"$MODULE/src/Ai/Class/Coa" "$ROOT/tests/coa-role-profiles.cpp"
"${compiler[@]}" -std=c++17 -Wall -Wextra -Werror \
  -I"$MODULE/src/Bot" "$ROOT/tests/coa-pilot-recruit.cpp" -o "$WORK/recruit-policy"
"$WORK/recruit-policy"
python3 "$ROOT/tests/validate-coa-brewing-healing.py" "$MODULE"
python3 "$ROOT/tests/validate-coa-pilot-prepare.py" "$SOURCE"
python3 "$ROOT/tests/validate-coa-travel.py" "$MODULE"
python3 "$ROOT/tests/validate-coa-talent-state.py" "$SOURCE"
echo "COA role, recruitment, healing, preparation, travel and talent-state regression checks passed."
