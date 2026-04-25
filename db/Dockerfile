# TimescaleDB with Oura init SQL baked in.
# Postgres runs files in /docker-entrypoint-initdb.d alphabetically on first boot.
FROM timescale/timescaledb-ha:pg16

USER root
COPY 01_schema.sql              /docker-entrypoint-initdb.d/01_schema.sql
COPY 02_continuous_aggregates.sql /docker-entrypoint-initdb.d/02_continuous_aggregates.sql
COPY 03_views.sql               /docker-entrypoint-initdb.d/03_views.sql
RUN chmod 644 /docker-entrypoint-initdb.d/*.sql

USER postgres
