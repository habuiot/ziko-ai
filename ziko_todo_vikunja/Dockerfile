# Deliberately isolated Home Assistant app: no /config mount, Docker socket,
# privileged access, Supervisor token, or host network permission.
# Vikunja binary is copied from the official upstream 2.8.0 image.
FROM ghcr.io/go-vikunja/vikunja:2.8.0 AS upstream

FROM alpine:3.22
RUN apk add --no-cache ca-certificates tzdata jq su-exec \
 && addgroup -g 1000 -S vikunja \
 && adduser -S -D -H -u 1000 -G vikunja vikunja
COPY --from=upstream /app/vikunja/vikunja /usr/local/bin/vikunja
COPY start.sh /usr/local/bin/start-zikotodo.sh
RUN chmod 0755 /usr/local/bin/vikunja /usr/local/bin/start-zikotodo.sh
EXPOSE 3456/tcp
CMD ["/usr/local/bin/start-zikotodo.sh"]
