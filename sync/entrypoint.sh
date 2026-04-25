#!/bin/bash
set -euo pipefail

wait_for_db() {
  until python -c "import psycopg, os; psycopg.connect(host=os.environ['POSTGRES_HOST'], port=os.environ.get('POSTGRES_PORT',5432), dbname=os.environ['POSTGRES_DB'], user=os.environ['POSTGRES_USER'], password=os.environ['POSTGRES_PASSWORD']).close()" 2>/dev/null; do
    echo "[entrypoint] waiting for postgres..."
    sleep 2
  done
}

# Railway / any cron-based scheduler: ONESHOT=1 → run once, exit.
# Local docker-compose: no ONESHOT → run once then daemonize with cron.
if [[ "${ONESHOT:-0}" = "1" ]]; then
  wait_for_db
  exec python oura_sync.py
fi

wait_for_db
echo "[entrypoint] initial sync"
python oura_sync.py || echo "[entrypoint] initial sync failed (will retry via cron)"

# Install crontab and tail log
echo "${SYNC_SCHEDULE:-0 */3 * * *} cd /app && OURA_PAT='${OURA_PAT}' POSTGRES_HOST='${POSTGRES_HOST}' POSTGRES_PORT='${POSTGRES_PORT:-5432}' POSTGRES_DB='${POSTGRES_DB}' POSTGRES_USER='${POSTGRES_USER}' POSTGRES_PASSWORD='${POSTGRES_PASSWORD}' python oura_sync.py >> /var/log/sync.log 2>&1" | crontab -

touch /var/log/sync.log
cron
echo "[entrypoint] cron started (schedule: ${SYNC_SCHEDULE:-0 */3 * * *})"
tail -F /var/log/sync.log
