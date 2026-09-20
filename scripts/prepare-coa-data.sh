#!/usr/bin/env bash
set -euo pipefail

CLIENT_DIR=""
SOURCE_DIR=""
OUTPUT_DIR="${COA_DATA_OUTPUT:-$HOME/wow-server-coa-dev-data}"
MPQCLI="${MPQCLI:-}"
BASE_DATA_VERSION="v20.0"

usage() {
  cat <<'USAGE'
Usage: ./scripts/prepare-coa-data.sh --client-dir DIR --source-dir DIR --mpqcli FILE [options]

Required:
  --client-dir DIR   Existing COA/Ascension client root containing Data
  --source-dir DIR   Checkout of jealous-sound/azerothcore-wotlk-coa
  --mpqcli FILE      Linux mpqcli executable

Options:
  --output DIR       New prepared-data directory (default: ~/wow-server-coa-dev-data)
  -h, --help         Show this help

The output directory must not already exist. Standard AzerothCore maps/vmaps/mmaps are downloaded from the
upstream client-data release, while DBCs are extracted from the supplied COA client and validated against the
selected COA source checkout. The client itself is read-only and is never modified.
USAGE
}

log() { printf '\033[0;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[0;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --client-dir) CLIENT_DIR="${2:-}"; shift 2 ;;
    --source-dir) SOURCE_DIR="${2:-}"; shift 2 ;;
    --mpqcli) MPQCLI="${2:-}"; shift 2 ;;
    --output) OUTPUT_DIR="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done

[[ -d "$CLIENT_DIR/Data" ]] || die "Client Data directory not found: $CLIENT_DIR/Data"
[[ -f "$SOURCE_DIR/apps/coa-dbc/client_dbc.py" ]] || die "COA source checkout is invalid: $SOURCE_DIR"
[[ -x "$MPQCLI" ]] || die "mpqcli is missing or not executable: $MPQCLI"
[[ ! -e "$OUTPUT_DIR" ]] || die "Output already exists: $OUTPUT_DIR"
command -v curl >/dev/null 2>&1 || die "curl is required."
command -v python3 >/dev/null 2>&1 || die "Python 3 is required."

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

log "Downloading standard map data $BASE_DATA_VERSION..."
curl --fail --location --retry 3 \
  "https://github.com/wowgaming/client-data/releases/download/$BASE_DATA_VERSION/data.zip" \
  --output "$work_dir/data.zip"
python3 -m zipfile -e "$work_dir/data.zip" "$work_dir/base"

mkdir -p "$OUTPUT_DIR"
for directory in maps vmaps mmaps; do
  [[ -d "$work_dir/base/$directory" ]] || die "Downloaded package is missing $directory"
  mv "$work_dir/base/$directory" "$OUTPUT_DIR/$directory"
done

log "Extracting the effective COA DBC set without modifying the client..."
python3 "$SOURCE_DIR/apps/coa-dbc/client_dbc.py" extract \
  "$CLIENT_DIR/Data" "$OUTPUT_DIR/dbc" --original --mpqcli "$MPQCLI"
python3 "$SOURCE_DIR/apps/coa-dbc/client_dbc.py" check "$OUTPUT_DIR/dbc"

log "Prepared COA server data at $OUTPUT_DIR"
