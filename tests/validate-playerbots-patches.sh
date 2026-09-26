#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git clone --quiet https://github.com/jealous-sound/azerothcore-wotlk-coa.git "$WORK/source"
git -C "$WORK/source" checkout --quiet --detach a8b28faac98d81b063bb81ff634037f71827d128
git -C "$WORK/source" apply "$ROOT/source-patches/playerbots-core.patch"
git clone --quiet https://github.com/mod-playerbots/mod-playerbots.git "$WORK/source/modules/mod-playerbots"
git -C "$WORK/source/modules/mod-playerbots" checkout --quiet --detach 619a06fc795a7220fd5c27d5a5aa4a2fbe383b72
git -C "$WORK/source/modules/mod-playerbots" apply "$ROOT/source-patches/playerbots-coa.patch"
git -C "$WORK/source" apply "$ROOT/source-patches/coa-local-qol-playerbots.patch"
git -C "$WORK/source" apply "$ROOT/source-patches/coa-progression-validation.patch"

test -f "$WORK/source/modules/mod-playerbots/conf/playerbots.conf.dist"
grep -q 'localStarterBag = 1004037' "$WORK/source/modules/mod-ascension-compat/src/AscensionCompat.cpp"
grep -q '"localspecstate", HandleLocalSpecStateCommand' "$WORK/source/modules/mod-ascension-compat/src/AscensionCompat.cpp"
grep -q 'MOD_PLAYERBOTS_FOUND' "$WORK/source/modules/CMakeLists.txt"
grep -q 'RandomBotCustomClassesOnly' "$WORK/source/modules/mod-playerbots/src/PlayerbotAIConfig.cpp"
grep -q 'info.rClass < 12' "$WORK/source/modules/mod-playerbots/src/Bot/RandomPlayerbotMgr.cpp"
grep -q 'rndBotAccountCandidates' "$WORK/source/modules/mod-playerbots/src/Bot/RandomPlayerbotMgr.cpp"
echo "Playerbots patches apply cleanly to their pinned revisions."
