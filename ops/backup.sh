#!/usr/bin/env bash
# Dump the oura database to ./backups/oura-<ISO-date>.sql.gz
# Idempotent, safe to run on a schedule.

set -euo pipefail

cd "$(dirname "$0")/.."

BACKUPS_DIR="backups"
mkdir -p "$BACKUPS_DIR"

# Load .env if present, so POSTGRES_USER / POSTGRES_DB are known.
if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
fi

USER="${POSTGRES_USER:-oura}"
DB="${POSTGRES_DB:-oura}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUPS_DIR/oura-${STAMP}.sql.gz"

echo "  backup → $OUT"
docker compose exec -T timescaledb pg_dump \
  -U "$USER" \
  -d "$DB" \
  --clean --if-exists --no-owner --no-privileges \
  | gzip -9 > "$OUT"

# Keep only the 14 most recent backups.
ls -1t "$BACKUPS_DIR"/oura-*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm --

SIZE="$(du -h "$OUT" | cut -f1)"
echo "  done ($SIZE)"
