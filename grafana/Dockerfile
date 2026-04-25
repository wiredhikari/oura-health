# Grafana with Oura dashboards + datasource provisioning baked in.
FROM grafana/grafana:11.3.0

# Dark theme by default; all anonymous dashboards disabled.
ENV GF_USERS_DEFAULT_THEME=dark \
    GF_AUTH_ANONYMOUS_ENABLED=false \
    GF_USERS_HOME_PAGE=/d/oura-today

COPY provisioning/ /etc/grafana/provisioning/
COPY dashboards/   /var/lib/grafana/dashboards/

# Railway mounts persistent volumes at /var/lib/grafana owned by root,
# but the grafana base image runs as user 472. We need to chown the
# volume on container start. Switch to root, install su-exec for the
# privilege drop, and wrap /run.sh with a chown+exec entrypoint.
USER root
RUN apk add --no-cache su-exec \
 && printf '#!/bin/sh\nset -e\nmkdir -p /var/lib/grafana/plugins\nchown -R 472:472 /var/lib/grafana\nexec su-exec 472:472 /run.sh "$@"\n' > /railway-entrypoint.sh \
 && chmod +x /railway-entrypoint.sh
ENTRYPOINT ["/railway-entrypoint.sh"]
