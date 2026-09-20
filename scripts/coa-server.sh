#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${COA_INSTALL_DIR:-$HOME/wow-server-coa-dev}"

usage() {
  cat <<'USAGE'
Usage: ./scripts/coa-server.sh [--dir DIR] COMMAND

Commands: start, stop, restart, status, logs, console, config
USAGE
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) INSTALL_DIR="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) break ;;
  esac
done

COMMAND="${1:-}"
[[ -n "$COMMAND" ]] || { usage; exit 1; }
[[ -f "$INSTALL_DIR/.env" && -f "$INSTALL_DIR/compose.yaml" ]] || die "No COA install found at $INSTALL_DIR"

compose() {
  (cd "$INSTALL_DIR" && docker compose --env-file .env -f compose.yaml "$@")
}

case "$COMMAND" in
  start) compose up -d ;;
  stop) compose stop ;;
  restart) compose restart authserver worldserver ;;
  status) compose ps ;;
  logs) compose logs -f --tail=200 worldserver authserver database ;;
  console) compose attach worldserver ;;
  config) compose config ;;
  *) die "Unknown command: $COMMAND" ;;
esac
