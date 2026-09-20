#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash -n "$ROOT/scripts/install-coa.sh"
bash -n "$ROOT/scripts/coa-server.sh"
bash -n "$ROOT/scripts/prepare-coa-data.sh"
bash -n "$ROOT/docker/bootstrap-world.sh"

grep -q 'ac-client-data-init' "$ROOT/compose.yaml" && {
  echo "ERROR: stock client-data downloader must not be present" >&2
  exit 1
}

grep -q 'COA_DATA_DIR' "$ROOT/compose.yaml"
grep -q 'condition: service_completed_successfully' "$ROOT/compose.yaml"
grep -q 'AC_DYNAMIC_XP_PRESET' "$ROOT/compose.yaml"
grep -q 'AC_SKILL_GAIN_CRAFTING' "$ROOT/compose.yaml"
grep -q 'AC_SKILL_GAIN_GATHERING' "$ROOT/compose.yaml"
grep -q 'AC_START_PLAYER_MONEY' "$ROOT/compose.yaml"
grep -q 'coa-local-qol.patch' "$ROOT/scripts/install-coa.sh"
grep -q 'localStarterBag = 1004037' "$ROOT/source-patches/coa-local-qol.patch"
grep -q 'sunwarmedFurlineDisplay = 99008' "$ROOT/source-patches/coa-local-qol.patch"
grep -q 'Opened Book of Artisans trainer' "$ROOT/source-patches/coa-local-qol.patch"
grep -q '(57500, 0, 48503' "$ROOT/source-patches/coa-local-qol.patch"

help_output="$(bash "$ROOT/scripts/install-coa.sh" --help)"
grep -q -- '--dry-run' <<< "$help_output"
grep -q -- '--data-dir' <<< "$help_output"

test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT
mkdir -p "$test_root/data/dbc" "$test_root/data/maps" "$test_root/data/vmaps" "$test_root/data/mmaps"
for number in {1..100}; do
  touch "$test_root/data/dbc/test-$number.dbc"
done
"$ROOT/scripts/install-coa.sh" --data-dir "$test_root/data" --dir "$test_root/runtime" --dry-run >/dev/null
[[ ! -e "$test_root/runtime" ]]

echo "All fast checks passed."
