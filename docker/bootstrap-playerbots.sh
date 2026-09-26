#!/usr/bin/env bash
set -euo pipefail

[[ "${COA_PLAYERBOTS_ENABLED:-0}" == "1" ]] || {
  echo "Playerbots is disabled; database bootstrap skipped."
  exit 0
}

credentials="$(mktemp)"
trap 'rm -f "$credentials"' EXIT
chmod 600 "$credentials"
cat > "$credentials" <<EOF
[client]
host=database
port=3306
user=root
password=$COA_DB_ROOT_PASSWORD
EOF

mysql --defaults-extra-file="$credentials" --execute="CREATE DATABASE IF NOT EXISTS acore_playerbots"
marker="coa_local_playerbots_bootstrap"
installed="$(mysql --defaults-extra-file="$credentials" --batch --skip-column-names acore_playerbots \
  --execute="SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='acore_playerbots' AND table_name='$marker'")"
[[ "$installed" == "0" ]] || {
  echo "Playerbots databases are already initialized."
  exit 0
}

import_tree() {
  local database="$1" directory="$2" sql
  while IFS= read -r -d '' sql; do
    echo "Importing $sql into $database"
    mysql --defaults-extra-file="$credentials" "$database" < "$sql"
  done < <(find "$directory" -maxdepth 1 -type f -name '*.sql' -print0 | sort -z)
}

module=/coa-source/modules/mod-playerbots/data/sql
[[ -d "$module/playerbots/base" ]] || { echo "Playerbots SQL is missing from the source tree." >&2; exit 1; }
import_tree acore_playerbots "$module/playerbots/base"
import_tree acore_playerbots "$module/playerbots/updates"
import_tree acore_characters "$module/characters/base"
import_tree acore_world "$module/world/base"
mysql --defaults-extra-file="$credentials" acore_playerbots \
  --execute="CREATE TABLE $marker (installed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
echo "Playerbots database bootstrap complete."
