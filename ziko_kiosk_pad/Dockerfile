FROM python:3.12-alpine
RUN apk add --no-cache openssl
WORKDIR /app
COPY app.py secure.py index.html access_2226_live.html ipad_kiosk_2026.html canonical_digitaltwin_v012.svg /app/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ZIKO_DATA_DIR=/data ZIKO_PORT=8096
EXPOSE 8096 8097 8098
CMD ["python3", "/app/app.py"]

