FROM python:3.13-alpine
RUN apk add --no-cache su-exec \
 && addgroup -S -g 1000 zikotodo \
 && adduser -S -D -u 1000 -G zikotodo zikotodo
WORKDIR /opt/zikotodo
COPY server.py panel.py acl.py admin_cli.py ./
COPY start.sh /usr/local/bin/start-zikotodo.sh
RUN chmod 0755 /usr/local/bin/start-zikotodo.sh \
 && chown -R zikotodo:zikotodo /opt/zikotodo
EXPOSE 8099
ENV PYTHONUNBUFFERED=1 ZIKO_GATEWAY_PORT=8099 ZIKO_TRUSTED_PROXY=172.30.32.2
CMD ["/usr/local/bin/start-zikotodo.sh"]
