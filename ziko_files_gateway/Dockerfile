FROM python:3.13-alpine
WORKDIR /opt/ziko-files-ingress
COPY gateway.py backend.crt ./
RUN addgroup -S zikofiles && adduser -S -D -G zikofiles zikofiles \
    && chmod 0644 /opt/ziko-files-ingress/backend.crt \
    && chown -R zikofiles:zikofiles /opt/ziko-files-ingress
USER zikofiles
EXPOSE 8098
ENV PYTHONUNBUFFERED=1
CMD ["python3", "/opt/ziko-files-ingress/gateway.py"]
