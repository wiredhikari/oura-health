# Grafana with Oura dashboards + datasource provisioning baked in.
FROM grafana/grafana:11.3.0

# Dark theme by default; all anonymous dashboards disabled.
ENV GF_USERS_DEFAULT_THEME=dark \
    GF_AUTH_ANONYMOUS_ENABLED=false \
    GF_USERS_HOME_PAGE=/d/oura-today

COPY provisioning/ /etc/grafana/provisioning/
COPY dashboards/   /var/lib/grafana/dashboards/
