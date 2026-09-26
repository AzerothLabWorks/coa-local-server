#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

UPSTREAM_REPO="${COA_UPSTREAM_REPO:-https://github.com/jealous-sound/azerothcore-wotlk-coa.git}"
UPSTREAM_REF="${COA_UPSTREAM_REF:-main}"
PLAYERBOTS_CORE_REF="a8b28faac98d81b063bb81ff634037f71827d128"
PLAYERBOTS_MODULE_REPO="https://github.com/mod-playerbots/mod-playerbots.git"
PLAYERBOTS_MODULE_REF="619a06fc795a7220fd5c27d5a5aa4a2fbe383b72"
PLAYERBOTS_CHARSECTIONS_SHA256="18fc8d23f6e66598ab1681a74f90239ebdf84b76f300db0865cdad7d042b833f"
PLAYERBOTS_EMOTESTEXTSOUND_SHA256="a4838f123580dbec5ae858bea51c3d8cc6ffed924203ceb50e81c196eebb1916"
INSTALL_DIR="${COA_INSTALL_DIR:-$HOME/wow-server-coa-dev}"
DATA_DIR="${COA_PREPARED_DATA_DIR:-}"
CLIENT_DIR=""
PLAYERBOTS_PACKAGE_DIR=""
WITH_PLAYERBOTS=false
UPSTREAM_REF_EXPLICIT=false
DRY_RUN=false
NO_START=false

usage() {
  cat <<'USAGE'
Usage: ./scripts/install-coa.sh --data-dir DIR [options]

Required:
  --data-dir DIR      Prepared server data containing dbc/maps/vmaps/mmaps

Options:
  --dir DIR           Runtime directory (default: ~/wow-server-coa-dev)
  --upstream-ref REF  Upstream branch, tag, or commit (default: main)
  --with-playerbots    Build the pinned open-source Playerbots core and module
  --client-dir DIR     Optionally install UnBot into this COA client
  --playerbots-package-dir DIR
                       Repack CoA-Bots directory containing Client/Interface/AddOns/UnBot
  --no-start          Prepare and build images, but do not start services
  --dry-run           Validate inputs and print the planned work only
  -h, --help          Show this help
USAGE
}

log() { printf '\033[0;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[0;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) INSTALL_DIR="${2:-}"; shift 2 ;;
    --data-dir) DATA_DIR="${2:-}"; shift 2 ;;
    --upstream-ref) UPSTREAM_REF="${2:-}"; UPSTREAM_REF_EXPLICIT=true; shift 2 ;;
    --with-playerbots) WITH_PLAYERBOTS=true; shift ;;
    --client-dir) CLIENT_DIR="${2:-}"; shift 2 ;;
    --playerbots-package-dir) PLAYERBOTS_PACKAGE_DIR="${2:-}"; shift 2 ;;
    --no-start) NO_START=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required."
}

absolute_path() {
  local path="$1"
  if command -v realpath >/dev/null 2>&1; then
    realpath "$path"
  else
    (cd "$(dirname "$path")" && printf '%s/%s\n' "$PWD" "$(basename "$path")")
  fi
}

validate_inputs() {
  [[ "$(uname -s)" == "Linux" ]] || die "Run this installer inside Linux or Ubuntu/WSL2."
  require_command git
  require_command docker
  require_command openssl
  require_command sha256sum
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required."
  docker info >/dev/null 2>&1 || die "Docker is not running or this user cannot access it."

  [[ -n "$DATA_DIR" ]] || die "--data-dir is required."
  [[ -d "$DATA_DIR" ]] || die "Prepared server data directory not found: $DATA_DIR"
  local required
  for required in dbc maps vmaps mmaps; do
    [[ -d "$DATA_DIR/$required" ]] || die "Missing required data directory: $DATA_DIR/$required"
  done

  local dbc_count
  dbc_count="$(find "$DATA_DIR/dbc" -maxdepth 1 -type f -iname '*.dbc' | wc -l)"
  (( dbc_count >= 100 )) || die "Only $dbc_count DBC files found; expected a complete COA DBC set (at least 100)."

  if [[ "$WITH_PLAYERBOTS" == true ]]; then
    if [[ "$UPSTREAM_REF_EXPLICIT" == true && "$UPSTREAM_REF" != "$PLAYERBOTS_CORE_REF" ]]; then
      die "--with-playerbots currently requires COA revision $PLAYERBOTS_CORE_REF."
    fi
    UPSTREAM_REF="$PLAYERBOTS_CORE_REF"
    local charsections_hash emotestextsound_hash
    charsections_hash="$(sha256sum "$DATA_DIR/dbc/CharSections.dbc" | awk '{print $1}')"
    emotestextsound_hash="$(sha256sum "$DATA_DIR/dbc/EmotesTextSound.dbc" | awk '{print $1}')"
    [[ "$charsections_hash" == "$PLAYERBOTS_CHARSECTIONS_SHA256" &&
       "$emotestextsound_hash" == "$PLAYERBOTS_EMOTESTEXTSOUND_SHA256" ]] ||
      die "Playerbots requires the matching CoA-Bots repack Data directory; these DBCs are incompatible."
  fi

  if [[ -n "$CLIENT_DIR" || -n "$PLAYERBOTS_PACKAGE_DIR" ]]; then
    [[ "$WITH_PLAYERBOTS" == true ]] || die "Client addon installation requires --with-playerbots."
    [[ -n "$CLIENT_DIR" && -n "$PLAYERBOTS_PACKAGE_DIR" ]] || die "Use --client-dir and --playerbots-package-dir together."
    [[ -d "$CLIENT_DIR/Interface/AddOns" ]] || die "Client AddOns directory not found: $CLIENT_DIR/Interface/AddOns"
    [[ -d "$PLAYERBOTS_PACKAGE_DIR/Client/Interface/AddOns/UnBot" ]] || die "UnBot not found below: $PLAYERBOTS_PACKAGE_DIR"
  fi

  DATA_DIR="$(absolute_path "$DATA_DIR")"
}

show_plan() {
  log "COA installation plan"
  printf '  Runtime:      %s\n' "$INSTALL_DIR"
  printf '  Upstream:     %s\n' "$UPSTREAM_REPO"
  printf '  Ref:          %s\n' "$UPSTREAM_REF"
  printf '  World DB:     bundled, verified upstream COA baseline\n'
  printf '  Server data:  %s\n' "$DATA_DIR"
  printf '  Playerbots:   %s\n' "$([[ "$WITH_PLAYERBOTS" == true ]] && printf yes || printf no)"
  printf '  Start stack:  %s\n' "$([[ "$NO_START" == true ]] && printf no || printf yes)"
}

prepare_runtime() {
  [[ ! -e "$INSTALL_DIR" ]] || die "Target already exists: $INSTALL_DIR (existing installs are never overwritten)."
  mkdir -p "$INSTALL_DIR/orchestration" "$INSTALL_DIR/state"

  log "Cloning COA source..."
  git clone "$UPSTREAM_REPO" "$INSTALL_DIR/source"
  git -C "$INSTALL_DIR/source" checkout --detach "$UPSTREAM_REF"
  if [[ "$WITH_PLAYERBOTS" == true ]]; then
    git -C "$INSTALL_DIR/source" apply "$REPO_ROOT/source-patches/playerbots-core.patch"
    git clone "$PLAYERBOTS_MODULE_REPO" "$INSTALL_DIR/source/modules/mod-playerbots"
    git -C "$INSTALL_DIR/source/modules/mod-playerbots" checkout --detach "$PLAYERBOTS_MODULE_REF"
    git -C "$INSTALL_DIR/source/modules/mod-playerbots" apply \
      "$REPO_ROOT/source-patches/playerbots-coa.patch"
    git -C "$INSTALL_DIR/source/modules/mod-playerbots" apply \
      "$REPO_ROOT/source-patches/playerbots-follow-mount.patch"
    git -C "$INSTALL_DIR/source/modules/mod-playerbots" apply \
      "$REPO_ROOT/source-patches/playerbots-coa-noncombat.patch"
    git -C "$INSTALL_DIR/source" apply "$REPO_ROOT/source-patches/coa-local-qol-playerbots.patch"
    git -C "$INSTALL_DIR/source" apply "$REPO_ROOT/source-patches/coa-progression-validation.patch"
    printf '%s\n' "$PLAYERBOTS_MODULE_REF" > "$INSTALL_DIR/state/playerbots-module-commit"
  else
    git -C "$INSTALL_DIR/source" apply "$REPO_ROOT/source-patches/coa-local-qol.patch"
  fi
  git -C "$INSTALL_DIR/source" rev-parse HEAD > "$INSTALL_DIR/state/upstream-commit"

  cp "$REPO_ROOT/compose.yaml" "$INSTALL_DIR/compose.yaml"
  cp "$REPO_ROOT/docker/world-bootstrap.Dockerfile" "$INSTALL_DIR/orchestration/world-bootstrap.Dockerfile"
  cp "$REPO_ROOT/docker/bootstrap-world.sh" "$INSTALL_DIR/orchestration/bootstrap-world.sh"
  cp "$REPO_ROOT/docker/bootstrap-playerbots.sh" "$INSTALL_DIR/orchestration/bootstrap-playerbots.sh"

  if [[ -n "$CLIENT_DIR" ]]; then
    if [[ -e "$CLIENT_DIR/Interface/AddOns/UnBot" ]]; then
      mv "$CLIENT_DIR/Interface/AddOns/UnBot" \
        "$CLIENT_DIR/Interface/AddOns/UnBot.backup.$(date +%Y%m%d%H%M%S)"
    fi
    cp -a "$PLAYERBOTS_PACKAGE_DIR/Client/Interface/AddOns/UnBot" "$CLIENT_DIR/Interface/AddOns/UnBot"
  fi

  local password user_id group_id source_dir orchestration_dir data_dir
  password="$(openssl rand -hex 24)"
  user_id="$(id -u)"
  group_id="$(id -g)"
  source_dir="$(absolute_path "$INSTALL_DIR/source")"
  orchestration_dir="$(absolute_path "$INSTALL_DIR/orchestration")"
  data_dir="$DATA_DIR"

  umask 077
  cat > "$INSTALL_DIR/.env" <<EOF
COMPOSE_PROJECT_NAME=coa-local
COA_SOURCE_DIR=$source_dir
COA_ORCHESTRATION_DIR=$orchestration_dir
COA_DATA_DIR=$data_dir
COA_DB_ROOT_PASSWORD=$password
COA_USER_ID=$user_id
COA_GROUP_ID=$group_id
COA_IMAGE_TAG=dev
COA_TIMEZONE=America/Los_Angeles
COA_REALM_ADDRESS=127.0.0.1
COA_DB_PORT=33306
COA_AUTH_PORT=33724
COA_WORLD_PORT=38085
COA_SOAP_PORT=37878
COA_XP_RATE=3
COA_PROFESSION_RATE=4
COA_STARTER_MONEY_COPPER=50000000
COA_PLAYERBOTS_ENABLED=$([[ "$WITH_PLAYERBOTS" == true ]] && printf 1 || printf 0)
COA_MIN_RANDOM_BOTS=12
COA_MAX_RANDOM_BOTS=12
COA_RANDOM_BOT_ACCOUNT_COUNT=120
COA_BREWING_PILOT_NAME=
EOF
  chmod 600 "$INSTALL_DIR/.env"
}

build_and_start() {
  log "Validating Compose configuration..."
  (cd "$INSTALL_DIR" && docker compose --env-file .env -f compose.yaml config --quiet)
  log "Building COA images from source. The first build can take a long time..."
  (cd "$INSTALL_DIR" && docker compose --env-file .env -f compose.yaml build)
  if [[ "$NO_START" == false ]]; then
    log "Starting COA services..."
    (cd "$INSTALL_DIR" && docker compose --env-file .env -f compose.yaml up -d)
  fi
}

main() {
  validate_inputs
  show_plan
  if [[ "$DRY_RUN" == true ]]; then
    log "Dry run complete; no files or containers were changed."
    return
  fi
  prepare_runtime
  build_and_start
  log "Installation prepared at $INSTALL_DIR"
  log "Recorded upstream commit: $(cat "$INSTALL_DIR/state/upstream-commit")"
  log "Use $REPO_ROOT/scripts/coa-server.sh --dir $INSTALL_DIR status"
}

main
