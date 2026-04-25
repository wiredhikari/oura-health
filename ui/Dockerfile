FROM nginx:1.27-alpine

# envsubst (from gettext) renders nginx.conf.template at container start so
# the same image works for both docker-compose and Railway.
RUN apk add --no-cache gettext

COPY nginx.conf.template /etc/nginx/nginx.conf.template
COPY proxy.conf          /etc/nginx/proxy.conf
COPY index.html          /usr/share/nginx/html/index.html
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost:${PORT:-80}/healthz || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
