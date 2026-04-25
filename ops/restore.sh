#!/usr/bin/env bash
# Restore the oura database from a gzipped pg_dump produced by ./backup.sh.
# Usage:  ops/restore.sh backups/oura-20260401T000000Z.sql.gz

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $0 <backup-file.sql.gz>" >&2
  exit 1
fi

FILE="$1"
if [ ! -f "$FILE" ]; then
  echo "not found: $FILE" >&2
  exit 1
fi

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
fi

USER="${POSTGRES_USER:-oura}"
DB="${POSTGRES_DB:-oura}"

echo "  restore ← $FILE"
gunzip -c "$FILE" | docker compose exec -T timescaledb psql -U "$USER" -d "$DB"
echo "  done"
