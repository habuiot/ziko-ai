FROM python:3.13-alpine
WORKDIR /opt/zdl-ingress
COPY gateway.py backend.crt start.sh ./
RUN apk add --no-cache su-exec && addgroup -S zdl && adduser -S -D -G zdl zdl && chmod 0644 /opt/zdl-ingress/backend.crt && chmod 0755 /opt/zdl-ingress/start.sh && chown -R zdl:zdl /opt/zdl-ingress
EXPOSE 8097
ENV PYTHONUNBUFFERED=1
CMD ["/opt/zdl-ingress/start.sh"]
