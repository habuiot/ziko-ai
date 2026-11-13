FROM python:3.13-alpine
RUN addgroup -S -g 1000 zikotodo && adduser -S -D -u 1000 -G zikotodo zikotodo
WORKDIR /opt/zikotodo
COPY server.py .
RUN chown -R zikotodo:zikotodo /opt/zikotodo
USER zikotodo
EXPOSE 8099
ENV PYTHONUNBUFFERED=1 ZIKO_GATEWAY_PORT=8099 ZIKO_TRUSTED_PROXY=172.30.32.2
CMD ["python", "/opt/zikotodo/server.py"]
