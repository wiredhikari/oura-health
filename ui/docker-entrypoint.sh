#!/bin/sh
# Render nginx.conf from the template using runtime env vars, then start nginx.
# Works for both docker-compose (defaults below) and Railway (overrides set
# in the service variables). The substitution is whitelisted so we don't
# accidentally interpolate $request_uri etc.
set -eu

: "${PORT:=80}"
: "${GRAFANA_HOST:=grafana}"
: "${GRAFANA_PORT:=3000}"
export PORT GRAFANA_HOST GRAFANA_PORT

envsubst '${PORT} ${GRAFANA_HOST} ${GRAFANA_PORT}' \
  < /etc/nginx/nginx.conf.template \
  > /etc/nginx/nginx.conf

echo "[ui] nginx serving :${PORT}, proxying grafana → ${GRAFANA_HOST}:${GRAFANA_PORT}"
exec nginx -g 'daemon off;'
