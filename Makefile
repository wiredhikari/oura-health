.PHONY: help up down restart logs ps build rebuild sync sync-full digest backup restore clean nuke shell-db shell-sync shell-api url sync-sql

# Default: show help
help:
	@echo ""
	@echo "  oura-health — cardiovascular age analytics stack"
	@echo ""
	@echo "  make up          Build + start all services in the background"
	@echo "  make down        Stop services (keep volumes)"
	@echo "  make restart     Restart all services"
	@echo "  make logs        Tail logs from all services"
	@echo "  make logs-sync   Tail only the sync service"
	@echo "  make ps          Show service status"
	@echo "  make build       Build images"
	@echo "  make rebuild     Rebuild images with --no-cache"
	@echo ""
	@echo "  make sync        Run an on-demand incremental Oura sync"
	@echo "  make sync-full   Run a full backfill from day zero (BACKFILL_DAYS)"
	@echo "  make digest      Run the weekly Claude digest now (writes DB + optional email)"
	@echo ""
	@echo "  make backup      Dump the database to ./backups/"
	@echo "  make restore f=<file>  Restore from a backup file"
	@echo ""
	@echo "  make shell-db    Open a psql shell"
	@echo "  make shell-sync  Open a shell in the sync container"
	@echo "  make shell-api   Open a shell in the api container"
	@echo "  make url         Print the app + dashboard URLs"
	@echo ""
	@echo "  make clean       Stop + remove containers (keep data)"
	@echo "  make nuke        Stop + remove containers AND volumes (destructive!)"
	@echo ""

up:
	docker compose up -d --build
	@echo ""
	@echo "Stack is starting. Give it ~30s for the first boot, then:"
	@$(MAKE) --no-print-directory url

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f --tail=200

logs-sync:
	docker compose logs -f --tail=200 sync

ps:
	docker compose ps

build:
	docker compose build

rebuild:
	docker compose build --no-cache

sync:
	docker compose exec sync python -u /app/oura_sync.py

sync-full:
	docker compose exec -e BACKFILL_DAYS=730 sync python -u /app/oura_sync.py

digest:
	docker compose --profile manual run --rm digest

backup:
	@mkdir -p backups
	@bash ops/backup.sh

restore:
	@if [ -z "$(f)" ]; then echo "usage: make restore f=backups/oura-YYYYMMDD.sql.gz"; exit 1; fi
	@bash ops/restore.sh "$(f)"

sync-sql:
	@# Copies sql/*.sql into db/ so the TimescaleDB image rebuild picks up changes.
	@# SQL is edited in sql/, db/ is the Docker build context.
	cp sql/01_schema.sql              db/01_schema.sql
	cp sql/02_continuous_aggregates.sql db/02_continuous_aggregates.sql
	cp sql/03_views.sql               db/03_views.sql
	cp sql/04_v2_schema.sql           db/04_v2_schema.sql
	@echo "  sql/ → db/ (rerun 'make rebuild' to apply)"

shell-db:
	docker compose exec timescaledb psql -U $${POSTGRES_USER:-oura} -d $${POSTGRES_DB:-oura}

shell-sync:
	docker compose exec sync bash

shell-api:
	docker compose exec api bash

url:
	@APP_PORT=$${APP_PORT:-3001}; \
	GF_PORT=$${GRAFANA_PORT:-3000}; \
	API_PORT=$${API_PORT:-8000}; \
	echo "  App:        http://localhost:$$APP_PORT          ← log in with APP_PASSCODE"; \
	echo "  Grafana:    http://localhost:$$GF_PORT          ← admin + GF_SECURITY_ADMIN_PASSWORD"; \
	echo "  API docs:   http://localhost:$$API_PORT/docs"; \
	echo "  Today:      http://localhost:$$GF_PORT/d/oura-today"

clean:
	docker compose down --remove-orphans

nuke:
	@echo "This will destroy all local data. Ctrl-C to abort."
	@sleep 3
	docker compose down -v --remove-orphans
