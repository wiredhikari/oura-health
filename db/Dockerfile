# TimescaleDB with Oura init SQL baked in.
# Postgres runs files in /docker-entrypoint-initdb.d alphabetically on first boot.
#
# Using the slim image (~200 MB) instead of -ha (~5 GB) — we don't need the
# Patroni / pgBackRest / PostGIS bundle. If you ever need pgvector for
# embeddings, install it via:
#   RUN apt-get update && apt-get install -y postgresql-16-pgvector
FROM timescale/timescaledb:latest-pg16

COPY 01_schema.sql                /docker-entrypoint-initdb.d/01_schema.sql
COPY 02_continuous_aggregates.sql /docker-entrypoint-initdb.d/02_continuous_aggregates.sql
COPY 03_views.sql                 /docker-entrypoint-initdb.d/03_views.sql
COPY 04_v2_schema.sql             /docker-entrypoint-initdb.d/04_v2_schema.sql
