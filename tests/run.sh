#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash -n "$ROOT/scripts/install-coa.sh"
bash -n "$ROOT/scripts/coa-server.sh"
bash -n "$ROOT/scripts/prepare-coa-data.sh"
bash -n "$ROOT/scripts/verify-coa-candidate.sh"
bash -n "$ROOT/docker/bootstrap-world.sh"
bash -n "$ROOT/docker/bootstrap-playerbots.sh"
bash -n "$ROOT/tests/validate-coa-ai.sh"
python3 "$ROOT/tests/test-staging.py"
python3 "$ROOT/tests/test-staging-restore-proof.py"
python3 "$ROOT/tests/test-candidate-verification.py"
python3 -B "$ROOT/tests/test-coa-range.py"
python3 -B "$ROOT/tests/test-client-patches.py"
python3 -B "$ROOT/tests/test_g1_installer.py"

for patch in "$ROOT"/source-patches/*.patch; do
  git apply --numstat "$patch" >/dev/null
done

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
grep -q 'AC_ASCENSION_COMPAT_DBC_DIRECTORY' "$ROOT/compose.yaml"
grep -q 'AC_PLAYERBOTS_DATABASE_INFO' "$ROOT/compose.yaml"
grep -q 'AC_PLAYERBOTS_UPDATES_ENABLE_DATABASES: 0' "$ROOT/compose.yaml"
grep -q 'AC_AI_PLAYERBOT_RANDOM_BOT_AUTOLOGIN: 1' "$ROOT/compose.yaml"
grep -q 'AC_AI_PLAYERBOT_RANDOM_BOT_CUSTOM_CLASSES_ONLY: 1' "$ROOT/compose.yaml"
grep -q 'COA_RANDOM_BOT_ACCOUNT_COUNT:-120' "$ROOT/compose.yaml"
grep -q 'playerbots-bootstrap' "$ROOT/compose.yaml"
grep -q 'coa-local-qol.patch' "$ROOT/scripts/install-coa.sh"
grep -q 'localStarterBag = 1004037' "$ROOT/source-patches/coa-local-qol.patch"
grep -q 'sunwarmedFurlineDisplay = 99008' "$ROOT/source-patches/coa-local-qol.patch"
grep -Fq 'player->CastSpell(player, 91737, true)' "$ROOT/source-patches/coa-local-qol.patch"
grep -Fq 'player->CastSpell(player, 91737, true)' "$ROOT/source-patches/coa-local-qol-playerbots.patch"
test -f "$ROOT/source-patches/coa-local-furline-spellbook.patch"
grep -Fq 'spells.push_back(91737)' "$ROOT/source-patches/coa-local-furline-spellbook.patch"
grep -q 'coa-local-furline-spellbook.patch' "$ROOT/scripts/install-coa.sh"
grep -q 'Opened Book of Artisans trainer' "$ROOT/source-patches/coa-local-qol.patch"
grep -q '(57500, 0, 48503' "$ROOT/source-patches/coa-local-qol.patch"
test -f "$ROOT/sql/rev_20260926_00_local_artisans_model_fallback.sql"
grep -q '(57500, 0, 48501' "$ROOT/sql/rev_20260926_00_local_artisans_model_fallback.sql"
grep -q 'rev_20260926_00_local_artisans_model_fallback.sql' "$ROOT/scripts/install-coa.sh"
grep -q 'itr->second->State = PLAYERSPELL_CHANGED' "$ROOT/source-patches/coa-local-qol-playerbots.patch"
grep -q '!player->GetSession()->IsBot()' "$ROOT/source-patches/coa-local-qol-playerbots.patch"
grep -q 'PLAYERBOTS_MODULE_REF="619a06fc' "$ROOT/scripts/install-coa.sh"
grep -q 'playerbots-core.patch' "$ROOT/scripts/install-coa.sh"
grep -q 'playerbots-coa.patch' "$ROOT/scripts/install-coa.sh"
grep -q 'coa-progression-validation.patch' "$ROOT/scripts/install-coa.sh"
grep -q 'COA_RANDOM_BOT_ACCOUNT_COUNT=120' "$ROOT/scripts/install-coa.sh"
for patch in playerbots-coa-roles playerbots-coa-heal-ranks playerbots-coa-pilot-recruit playerbots-coa-pilot-reservation coa-bot-pilot-prepare playerbots-coa-combat-travel playerbots-coa-riding-preservation coa-talent-state; do
  test -s "$ROOT/source-patches/$patch.patch"
  grep -q "$patch.patch" "$ROOT/scripts/install-coa.sh"
  grep -q "$patch.patch" "$ROOT/tests/validate-playerbots-patches.sh"
done
grep -q 'COA_TEST_PILOT_NAMES' "$ROOT/compose.yaml"
grep -q 'COA_TEST_PILOT_NAMES=' "$ROOT/scripts/install-coa.sh"
for setting in COA_BOT_MIN_LEVEL COA_BOT_MAX_LEVEL COA_BOT_RIDING_MIN_LEVEL COA_BOT_AUTO_TRADE_ON_ITEM_MENTION COA_BOTS_PER_INTERVAL COA_BOT_STATS_INTERVAL COA_WORLD_STATS_INTERVAL_MS COA_WORLD_SLOW_TICK_MS; do
  grep -q "$setting" "$ROOT/compose.yaml"
  grep -q "$setting=" "$ROOT/scripts/install-coa.sh"
done
for tier in GROUND FAST_GROUND FLY FAST_FLY; do
  grep -Fq "AC_AI_PLAYERBOT_USE_${tier}_MOUNT_AT_MIN_LEVEL: \${COA_BOT_RIDING_MIN_LEVEL:-1}" "$ROOT/compose.yaml"
done
grep -q 'player->getClass() >= 12' "$ROOT/source-patches/playerbots-coa.patch"
grep -q 'randomBotCustomClassesOnly' "$ROOT/source-patches/playerbots-coa.patch"
test -s "$ROOT/client-patches/coa-range/LibRangeCheck-2.0.lua"
test -s "$ROOT/client-patches/coa-range/WeakAuras-GetRange.patch"
if grep -q 'cp .*client-addons/COAWeakAurasRange' "$ROOT/scripts/install-coa.sh"; then
  echo "ERROR: the retired spell-specific range helper must not be installed" >&2
  exit 1
fi

help_output="$(bash "$ROOT/scripts/install-coa.sh" --help)"
grep -q -- '--dry-run' <<< "$help_output"
grep -q -- '--data-dir' <<< "$help_output"
grep -q -- '--with-playerbots' <<< "$help_output"

test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT
mkdir -p "$test_root/data/dbc" "$test_root/data/maps" "$test_root/data/vmaps" "$test_root/data/mmaps"
mkdir -p "$test_root/client/Interface/AddOns"
mkdir -p "$test_root/bin"
# Dry-run checks must never require or operate a real Docker daemon.
cat > "$test_root/bin/docker" <<'SH'
#!/usr/bin/env bash
if [[ "$*" == 'compose version' || "$*" == 'info' ]]; then
  exit 0
fi
printf 'Unexpected Docker mutation in dry-run test: %s\n' "$*" >&2
exit 1
SH
chmod 700 "$test_root/bin/docker"
for number in {1..100}; do
  touch "$test_root/data/dbc/test-$number.dbc"
done
PATH="$test_root/bin:$PATH" "$ROOT/scripts/install-coa.sh" --data-dir "$test_root/data" --dir "$test_root/runtime" --dry-run >/dev/null
PATH="$test_root/bin:$PATH" "$ROOT/scripts/install-coa.sh" --data-dir "$test_root/data" --dir "$test_root/runtime" \
  --client-dir "$test_root/client" --dry-run >/dev/null
[[ ! -e "$test_root/runtime" ]]
[[ ! -e "$test_root/client/Interface/AddOns/COAWeakAurasRange" ]]

echo "All fast checks passed."
