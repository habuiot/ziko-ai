FROM python:3.13-alpine
WORKDIR /opt/ziko-warehouse-ingress
COPY gateway.py ./gateway.py
RUN addgroup -S zikowh && adduser -S -D -G zikowh zikowh && chown -R zikowh:zikowh /opt/ziko-warehouse-ingress
USER zikowh
EXPOSE 8099
ENV PYTHONUNBUFFERED=1
CMD ["python3", "/opt/ziko-warehouse-ingress/gateway.py"]
