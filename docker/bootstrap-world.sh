#!/usr/bin/env bash
set -euo pipefail

[[ -n "${COA_DB_ROOT_PASSWORD:-}" ]] || {
  echo "COA_DB_ROOT_PASSWORD is required" >&2
  exit 1
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

python3.12 /coa-source/apps/coa-world/world_data.py verify

# MySQL's container health check can briefly succeed against the temporary
# initialization server just before it is stopped. Wait for the final server
# to accept remote queries so first-time Compose startup is deterministic.
for attempt in {1..30}; do
  if mysql --defaults-extra-file="$credentials" --batch --skip-column-names \
    --execute="SELECT 1" >/dev/null 2>&1; then
    break
  fi

  if [[ "$attempt" == "30" ]]; then
    echo "MySQL did not become ready for COA world bootstrap." >&2
    exit 1
  fi

  sleep 2
done

if [[ "${COA_PLAYERBOTS_ENABLED:-0}" == "1" ]]; then
  mysql --defaults-extra-file="$credentials" \
    --execute="CREATE DATABASE IF NOT EXISTS acore_playerbots"
fi

table_count="$(mysql --defaults-extra-file="$credentials" --batch --skip-column-names \
  --execute="SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='acore_world'")"
ledger_count="$(mysql --defaults-extra-file="$credentials" --batch --skip-column-names \
  --execute="SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='acore_world' AND table_name='updates'")"

if [[ "$table_count" == "0" ]]; then
  python3.12 /coa-source/apps/coa-world/world_data.py bootstrap \
    --defaults-file "$credentials" \
    --database acore_world
elif [[ "$ledger_count" == "1" ]]; then
  echo "An initialized COA world database already exists; bootstrap is not repeated."
else
  echo "The COA world schema is non-empty but has no completed migration ledger." >&2
  echo "This may be a partial import; restore a backup or recreate only the COA database volume." >&2
  exit 1
fi
