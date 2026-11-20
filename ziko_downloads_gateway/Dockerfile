FROM python:3.13-alpine
WORKDIR /opt/zdl-ingress
COPY gateway.py backend.crt ./
RUN addgroup -S zdl && adduser -S -D -G zdl zdl     && chmod 0644 /opt/zdl-ingress/backend.crt     && chown -R zdl:zdl /opt/zdl-ingress
USER zdl
EXPOSE 8097
ENV PYTHONUNBUFFERED=1
CMD ["python3", "/opt/zdl-ingress/gateway.py"]
