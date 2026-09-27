#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash -n "$ROOT/scripts/install-coa.sh"
bash -n "$ROOT/scripts/coa-server.sh"
bash -n "$ROOT/scripts/prepare-coa-data.sh"
bash -n "$ROOT/docker/bootstrap-world.sh"
bash -n "$ROOT/docker/bootstrap-playerbots.sh"

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
grep -q 'player->getClass() >= 12' "$ROOT/source-patches/playerbots-coa.patch"
grep -q 'randomBotCustomClassesOnly' "$ROOT/source-patches/playerbots-coa.patch"
test -f "$ROOT/client-addons/COAWeakAurasRange/COAWeakAurasRange.toc"
test -f "$ROOT/client-addons/COAWeakAurasRange/COAWeakAurasRange.lua"
grep -q 'Dependencies: WeakAuras' "$ROOT/client-addons/COAWeakAurasRange/COAWeakAurasRange.toc"
grep -q 'wa.IsSpellInRange(probe\[1\], unit) == 1' "$ROOT/client-addons/COAWeakAurasRange/COAWeakAurasRange.lua"
grep -q 'backup_client_addon COAWeakAurasRange' "$ROOT/scripts/install-coa.sh"

help_output="$(bash "$ROOT/scripts/install-coa.sh" --help)"
grep -q -- '--dry-run' <<< "$help_output"
grep -q -- '--data-dir' <<< "$help_output"
grep -q -- '--with-playerbots' <<< "$help_output"

test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT
mkdir -p "$test_root/data/dbc" "$test_root/data/maps" "$test_root/data/vmaps" "$test_root/data/mmaps"
mkdir -p "$test_root/client/Interface/AddOns"
for number in {1..100}; do
  touch "$test_root/data/dbc/test-$number.dbc"
done
"$ROOT/scripts/install-coa.sh" --data-dir "$test_root/data" --dir "$test_root/runtime" --dry-run >/dev/null
"$ROOT/scripts/install-coa.sh" --data-dir "$test_root/data" --dir "$test_root/runtime" \
  --client-dir "$test_root/client" --dry-run >/dev/null
[[ ! -e "$test_root/runtime" ]]
[[ ! -e "$test_root/client/Interface/AddOns/COAWeakAurasRange" ]]

echo "All fast checks passed."
