FROM python:3.13-alpine
WORKDIR /opt/ziko-whiteboard-ingress
COPY gateway.py ./gateway.py
RUN addgroup -S zikowb && adduser -S -D -G zikowb zikowb && chown -R zikowb:zikowb /opt/ziko-whiteboard-ingress
USER zikowb
EXPOSE 8097
ENV PYTHONUNBUFFERED=1
CMD ["python3", "/opt/ziko-whiteboard-ingress/gateway.py"]
