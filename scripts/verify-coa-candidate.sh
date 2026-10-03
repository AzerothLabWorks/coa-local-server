#!/usr/bin/env bash
set -euo pipefail

mode="${1:-verify}"
if [[ $# -gt 1 || ( "$mode" != verify && "$mode" != plan ) ]]; then
    printf 'Usage: %s [verify|plan]\n' "$0" >&2
    exit 2
fi

source_dir="${COA_G1_SOURCE_DIR:-/home/ryan/wow-server-coa-g1-candidate-source}"
build_dir="${COA_G1_BUILD_DIR:-/home/ryan/wow-server-coa-g1-candidate-build}"
data_dir="${COA_G1_DATA_DIR:-/home/ryan/wow-server-coa-g1-data-20261001}"
cache_dir="${COA_G1_CCACHE_DIR:-/home/ryan/wow-server-coa-g1-candidate-ccache}"
toolchain="${COA_G1_TOOLCHAIN_IMAGE:-coa-local/g1-toolchain@sha256:52d237189ca46c098a379a77ae464f7c696f3e71718bd04dc46c9ff9581db6e2}"
source_pin=d48a1123153a3c39e1eaafb7714b375ee67e7689

for directory in "$source_dir" "$build_dir" "$data_dir" "$cache_dir"; do
    if [[ ! -d "$directory" ]]; then
        printf 'Candidate prerequisite directory is missing: %s\n' "$directory" >&2
        exit 1
    fi
    resolved="$(realpath "$directory")"
    case "$resolved" in
        /|*/wow-server-coa-dev|*/wow-server-coa-dev/*|*/wow-server-coa-playerbots-source|*/wow-server-coa-playerbots-source/*|*/wow-server-coa-staging|*/wow-server-coa-staging/*)
            printf 'Refusing a live or accepted-baseline directory: %s\n' "$resolved" >&2
            exit 1
            ;;
    esac
done

source_dir="$(realpath "$source_dir")"
build_dir="$(realpath "$build_dir")"
data_dir="$(realpath "$data_dir")"
cache_dir="$(realpath "$cache_dir")"

if [[ "$source_dir" == "$build_dir" || "$source_dir" == "$cache_dir" || "$build_dir" == "$cache_dir" ]]; then
    printf 'Candidate source, build and cache directories must be distinct.\n' >&2
    exit 1
fi
if [[ "$(git -C "$source_dir" rev-parse HEAD)" != "$source_pin" ]]; then
    printf 'Candidate HEAD does not match the reviewed G1 source pin.\n' >&2
    exit 1
fi
if [[ ! -f "$source_dir/conf/verify-all.json" || ! -f "$data_dir/dbc/Spell.dbc" ]]; then
    printf 'Candidate verification settings or qualified Spell.dbc is missing.\n' >&2
    exit 1
fi

python3 - "$source_dir/conf/verify-all.json" "$build_dir" "$data_dir/dbc" <<'PY'
import json
from pathlib import Path
import sys

try:
    settings = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if not isinstance(settings, dict):
        raise ValueError('Candidate verification settings must be a JSON object')
    for key, expected in zip(('build_directory', 'dbc_directory'), sys.argv[2:]):
        value = settings.get(key)
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError(f'Candidate {key} must be an absolute configured path')
        if Path(value).resolve() != Path(expected).resolve():
            raise ValueError(f'Candidate {key} does not match the selected directory')
except (OSError, ValueError, TypeError) as error:
    raise SystemExit(str(error))
PY

command=(python3 -B tools/verify_all.py --stages source,build,unit,harness
    --base "$source_pin" --harness talent_state companion_loot --jobs 4)
if [[ "$mode" == plan ]]; then
    command+=(--plan)
fi

docker run --rm --user "$(id -u):$(id -g)" --cpus=4 --memory=10g --memory-swap=12g \
    --mount "type=bind,source=$source_dir,target=$source_dir" \
    --mount "type=bind,source=$build_dir,target=$build_dir" \
    --mount "type=bind,source=$data_dir,target=$data_dir,readonly" \
    --mount "type=bind,source=$cache_dir,target=/ccache" \
    --workdir "$source_dir" "$toolchain" "${command[@]}"
