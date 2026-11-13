FROM python:3.13-alpine
RUN apk add --no-cache su-exec tzdata \
 && addgroup -S -g 1001 zikocommand \
 && adduser -S -D -u 1001 -G zikocommand zikocommand
WORKDIR /opt/ziko-command
COPY engine.py server.py ./
COPY web/ ./web/
COPY start.sh /usr/local/bin/ziko-command-start
RUN chmod 0755 /usr/local/bin/ziko-command-start \
 && chown -R zikocommand:zikocommand /opt/ziko-command
ENV PYTHONUNBUFFERED=1 ZIKO_COMMAND_PORT=8100 ZIKO_TRUSTED_PROXY=172.30.32.2
EXPOSE 8100
CMD ["/usr/local/bin/ziko-command-start"]
